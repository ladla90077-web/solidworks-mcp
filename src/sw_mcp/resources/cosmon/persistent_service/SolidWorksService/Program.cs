using System;

namespace CosmonSWService
{
    /// <summary>
    /// Entry point for the CosmonSWServiceSW (SolidWorks version).
    /// 
    /// This service connects to SolidWorks and provides model state retrieval capabilities
    /// via the SolidWorksRouter.
    /// 
    /// On startup, the service generates a unique pipe name (GUID-based) and outputs it
    /// to stdout in the format: PIPE_READY:&lt;pipe_name&gt;
    /// 
    /// The Python service manager reads this line to know which pipe to connect to.
    /// This ensures each service instance has a unique pipe, avoiding conflicts.
    /// </summary>
    class Program
    {
        private const string PIPE_NAME_PREFIX = "CosmonSWService_";

        static void Main(string[] args)
        {
            // Startup canary: Python checks for this line to detect antivirus interference.
            Console.WriteLine("COSMON_EXE_STARTED");
            Console.Out.Flush();

            // Generate unique pipe name for this instance using GUID
            // Format: CosmonSWService_<guid> (32 hex chars, no dashes)
            string pipeName = PIPE_NAME_PREFIX + Guid.NewGuid().ToString("N");

            // Output pipe name FIRST, before any other output
            // Python service manager reads this line to know which pipe to connect to
            // Format: PIPE_READY:<pipe_name>
            Console.WriteLine($"PIPE_READY:{pipeName}");
            Console.Out.Flush();  // Ensure it's written immediately

            Console.WriteLine("[INFO] CosmonSWServiceSW starting...");
            Console.WriteLine($"[INFO] Pipe name: {pipeName}");
            Console.WriteLine($"[INFO] Process ID: {System.Diagnostics.Process.GetCurrentProcess().Id}");

            // Create router (SolidWorks connection will be initialized lazily in PreTaskCheck)
            var router = new SolidWorksRouter();
            Console.WriteLine("[INFO] SolidWorksRouter created");
            Console.WriteLine($"[INFO] Available tasks: {string.Join(", ", router.GetAvailableTasks())}");

            // Create and run server
            var server = new PipeServer(pipeName, router);

            // Set up signal handlers for graceful shutdown
            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true;
                Console.WriteLine("[INFO] Shutdown signal received (Ctrl+C)");
                server.RequestShutdown();
            };

            AppDomain.CurrentDomain.ProcessExit += (sender, e) =>
            {
                Console.WriteLine("[INFO] Process exit signal received");
                server.RequestShutdown();
            };

            // Run the server (blocks until shutdown)
            try
            {
                server.Run();
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[FATAL] Server error: {ex.Message}");
                Console.Error.WriteLine(ex.StackTrace);
                Environment.Exit(1);
            }
            finally
            {
                // Clean up SolidWorks connection
                router.Dispose();
            }

            Console.WriteLine("[INFO] CosmonSWServiceSW exited");
        }
    }
}

