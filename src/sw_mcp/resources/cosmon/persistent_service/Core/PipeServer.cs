using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Text;

namespace CosmonSWService
{
    /// <summary>
    /// Named pipe server that routes requests to an ITaskRouter.
    /// 
    /// The server handles:
    /// - Pipe lifecycle (create, accept connections, close)
    /// - Request/response protocol (length-prefixed JSON)
    /// - Built-in requests (shutdown)
    /// - Task routing via ITaskRouter (pre_task_check, execute_task)
    /// </summary>
    public class PipeServer
    {
        private readonly string _pipeName;
        private readonly ITaskRouter _router;
        private bool _running;

        /// <summary>
        /// Create a new PipeServer.
        /// </summary>
        /// <param name="pipeName">Name of the pipe (without \\.\pipe\ prefix).</param>
        /// <param name="router">Router to handle task requests.</param>
        public PipeServer(string pipeName, ITaskRouter router)
        {
            _pipeName = pipeName;
            _router = router;
            _running = false;
        }

        /// <summary>
        /// Run the server. Blocks until shutdown is requested.
        /// </summary>
        public void Run()
        {
            _running = true;
            Console.WriteLine($"[INFO] PipeServer starting on pipe: {_pipeName}");

            while (_running)
            {
                try
                {
                    ProcessNextConnection();
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[ERROR] Connection error: {ex.Message}");
                    // Continue accepting connections
                }
            }

            Console.WriteLine("[INFO] PipeServer stopped");
        }

        /// <summary>
        /// Request the server to stop.
        /// </summary>
        public void RequestShutdown()
        {
            _running = false;
        }

        private void ProcessNextConnection()
        {
            using (var pipeServer = new NamedPipeServerStream(
                _pipeName,
                PipeDirection.InOut,
                NamedPipeServerStream.MaxAllowedServerInstances,
                PipeTransmissionMode.Message,
                PipeOptions.Asynchronous))
            {
                // Wait for connection with periodic shutdown check
                var waitHandle = pipeServer.BeginWaitForConnection(null, null);

                while (!waitHandle.IsCompleted)
                {
                    if (!_running)
                    {
                        try { pipeServer.Close(); } catch { }
                        return;
                    }
                    waitHandle.AsyncWaitHandle.WaitOne(100);
                }

                try
                {
                    pipeServer.EndWaitForConnection(waitHandle);
                }
                catch (IOException)
                {
                    return; // Client disconnected or pipe closed
                }
                catch (ObjectDisposedException)
                {
                    return; // Pipe closed during shutdown
                }

                try
                {
                    // Read request
                    string requestJson = ReadMessage(pipeServer);
                    if (string.IsNullOrEmpty(requestJson))
                    {
                        Console.WriteLine("[WARN] Empty request received");
                        return;
                    }

                    // Parse and handle request
                    ServiceRequest request = Protocol.ParseRequest(requestJson);
                    if (request == null)
                    {
                        var errorResponse = Protocol.ErrorResponse(null, "ParseError", "Failed to parse request JSON");
                        WriteMessage(pipeServer, Protocol.SerializeResponse(errorResponse));
                        return;
                    }

                    // Handle request
                    ServiceResponse response = HandleRequest(request);

                    // Send response
                    WriteMessage(pipeServer, Protocol.SerializeResponse(response));
                }
                catch (IOException ex)
                {
                    Console.Error.WriteLine($"[ERROR] Pipe I/O error: {ex.Message}");
                }
            }
        }

        private ServiceResponse HandleRequest(ServiceRequest request)
        {
            Console.WriteLine($"[INFO] Handling request: {request.RequestType} (id: {request.RequestId})");

            // Handle built-in requests
            switch (request.RequestType)
            {
                case Protocol.REQUEST_SHUTDOWN:
                    return HandleShutdown(request);
            }

            // All other requests go through the router
            return HandleTaskRequest(request);
        }

        private ServiceResponse HandleShutdown(ServiceRequest request)
        {
            Console.WriteLine("[INFO] Shutdown request received");
            _running = false;
            return Protocol.SuccessResponse(request.RequestId);
        }

        private ServiceResponse HandleTaskRequest(ServiceRequest request)
        {
            // Run pre-task check with validation args
            TaskCheckResult check;
            try
            {
                check = _router.PreTaskCheck(request.PreTaskCheckArgs);
            }
            catch (Exception ex)
            {
                // PreTaskCheck threw an exception
                Console.Error.WriteLine($"[ERROR] PreTaskCheck threw: {ex.GetType().Name}: {ex.Message}");
                return Protocol.ErrorResponse(request.RequestId, ex.GetType().Name, ex.Message);
            }

            if (!check.CanProceed)
            {
                return Protocol.ErrorResponse(
                    request.RequestId,
                    "ReportedError",
                    check.ErrorMessage ?? "Pre-task check failed"
                );
            }

            // Execute task
            try
            {
                var result = _router.ExecuteTask(request.RequestType, request.Args);
                return Protocol.SuccessResponse(request.RequestId, result);
            }
            catch (ArgumentException ex)
            {
                // Unknown task or invalid arguments
                return Protocol.ErrorResponse(request.RequestId, "ArgumentError", ex.Message);
            }
            catch (Exception ex)
            {
                // Task execution failed
                Console.Error.WriteLine($"[ERROR] Task failed: {ex.GetType().Name}: {ex.Message}");
                return Protocol.ErrorResponse(request.RequestId, ex.GetType().Name, ex.Message);
            }
        }

        /// <summary>
        /// Read a length-prefixed message from the pipe.
        /// </summary>
        private static string ReadMessage(NamedPipeServerStream pipe)
        {
            // Read length prefix (4 bytes, little-endian)
            byte[] lengthBuffer = new byte[4];
            int bytesRead = pipe.Read(lengthBuffer, 0, 4);
            if (bytesRead < 4)
                return null;

            int messageLength = BitConverter.ToInt32(lengthBuffer, 0);
            if (messageLength <= 0 || messageLength > 100 * 1024 * 1024) // Max 100MB
                return null;

            // Read message body
            byte[] messageBuffer = new byte[messageLength];
            int totalRead = 0;
            while (totalRead < messageLength)
            {
                bytesRead = pipe.Read(messageBuffer, totalRead, messageLength - totalRead);
                if (bytesRead == 0)
                    break;
                totalRead += bytesRead;
            }

            if (totalRead < messageLength)
                return null;

            return Encoding.UTF8.GetString(messageBuffer);
        }

        /// <summary>
        /// Write a length-prefixed message to the pipe.
        /// </summary>
        private static void WriteMessage(NamedPipeServerStream pipe, string message)
        {
            byte[] messageBytes = Encoding.UTF8.GetBytes(message);
            byte[] lengthBytes = BitConverter.GetBytes(messageBytes.Length);

            pipe.Write(lengthBytes, 0, 4);
            pipe.Write(messageBytes, 0, messageBytes.Length);
            pipe.Flush();
        }
    }
}
