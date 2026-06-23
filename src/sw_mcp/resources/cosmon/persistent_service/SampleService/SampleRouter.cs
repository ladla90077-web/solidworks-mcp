using System;
using System.Collections.Generic;
using System.Threading;

namespace CosmonSWService
{
    /// <summary>
    /// Sample router implementation for testing.
    /// 
    /// This is a toy implementation with sample tasks that don't depend on SolidWorks.
    /// Use this to test the pipe server infrastructure.
    /// </summary>
    public class SampleRouter : ITaskRouter
    {
        // Task names
        public const string TASK_ECHO = "echo";
        public const string TASK_ADD = "add";
        public const string TASK_SLEEP = "sleep";
        public const string TASK_FAIL = "fail";
        public const string TASK_GET_STATE = "get_state";
        public const string TASK_SET_STATE = "set_state";
        public const string TASK_SLOW_OPERATION = "slow_operation";
        public const string TASK_LARGE_OUTPUT = "large_output";
        public const string TASK_OUTPUT_THEN_HANG = "output_then_hang";

        // Sample state - demonstrates how router can hold application state
        private readonly Dictionary<string, object> _state = new Dictionary<string, object>();
        private bool _isReady = true;

        /// <summary>
        /// Create a new SampleRouter.
        /// </summary>
        /// <param name="startReady">Whether the router starts in ready state.</param>
        public SampleRouter(bool startReady = true)
        {
            _isReady = startReady;
        }

        /// <summary>
        /// Set the ready state (for testing pre-task checks).
        /// </summary>
        public void SetReady(bool ready)
        {
            _isReady = ready;
        }

        public TaskCheckResult PreTaskCheck(Dictionary<string, object> preTaskCheckArgs)
        {
            // Check for test-triggered behaviors first (via preTaskCheckArgs)
            if (preTaskCheckArgs != null)
            {
                // force_throw: true - throw an exception (for testing exception handling)
                if (preTaskCheckArgs.ContainsKey("force_throw"))
                {
                    var forceThrow = Convert.ToBoolean(preTaskCheckArgs["force_throw"]);
                    if (forceThrow)
                    {
                        var errorMessage = preTaskCheckArgs.ContainsKey("error_message")
                            ? preTaskCheckArgs["error_message"]?.ToString()
                            : "PreTaskCheck threw exception for testing";

                        throw new InvalidOperationException(errorMessage);
                    }
                }

                // force_fail: true - return failure (for testing CanProceed=false)
                if (preTaskCheckArgs.ContainsKey("force_fail"))
                {
                    var forceFail = Convert.ToBoolean(preTaskCheckArgs["force_fail"]);
                    if (forceFail)
                    {
                        var errorMessage = preTaskCheckArgs.ContainsKey("error_message")
                            ? preTaskCheckArgs["error_message"]?.ToString()
                            : "PreTaskCheck forced to fail for testing";

                        return TaskCheckResult.Failure(errorMessage);
                    }
                }

                // require_state: "key" - fail if state key doesn't exist
                if (preTaskCheckArgs.ContainsKey("require_state"))
                {
                    var requiredKey = preTaskCheckArgs["require_state"]?.ToString();
                    if (!string.IsNullOrEmpty(requiredKey) && !_state.ContainsKey(requiredKey))
                    {
                        return TaskCheckResult.Failure(
                            $"Required state key '{requiredKey}' not found"
                        );
                    }
                }
            }

            // Normal ready check
            if (!_isReady)
            {
                return TaskCheckResult.Failure("Router is not ready. Call SetReady(true) first.");
            }
            return TaskCheckResult.Success();
        }

        public Dictionary<string, object> ExecuteTask(string taskName, Dictionary<string, object> taskArgs)
        {
            switch (taskName)
            {
                case TASK_ECHO:
                    return ExecuteEcho(taskArgs);

                case TASK_ADD:
                    return ExecuteAdd(taskArgs);

                case TASK_SLEEP:
                    return ExecuteSleep(taskArgs);

                case TASK_FAIL:
                    return ExecuteFail(taskArgs);

                case TASK_GET_STATE:
                    return ExecuteGetState(taskArgs);

                case TASK_SET_STATE:
                    return ExecuteSetState(taskArgs);

                case TASK_SLOW_OPERATION:
                    return ExecuteSlowOperation(taskArgs);

                case TASK_LARGE_OUTPUT:
                    return ExecuteLargeOutput(taskArgs);

                case TASK_OUTPUT_THEN_HANG:
                    return ExecuteOutputThenHang(taskArgs);

                default:
                    throw new ArgumentException($"Unknown task: {taskName}");
            }
        }

        public IEnumerable<string> GetAvailableTasks()
        {
            return new[]
            {
                TASK_ECHO,
                TASK_ADD,
                TASK_SLEEP,
                TASK_FAIL,
                TASK_GET_STATE,
                TASK_SET_STATE,
                TASK_SLOW_OPERATION,
                TASK_LARGE_OUTPUT,
                TASK_OUTPUT_THEN_HANG
            };
        }

        // ============================================================
        // Sample Task Implementations
        // ============================================================

        /// <summary>
        /// Echo task - returns whatever was passed in.
        /// Args: { "message": "hello" }
        /// Returns: { "echoed": "hello" }
        /// </summary>
        private Dictionary<string, object> ExecuteEcho(Dictionary<string, object> args)
        {
            var message = args != null && args.ContainsKey("message") 
                ? args["message"]?.ToString() 
                : "(no message)";

            return new Dictionary<string, object>
            {
                ["echoed"] = message
            };
        }

        /// <summary>
        /// Add task - adds two numbers.
        /// Args: { "a": 1, "b": 2 }
        /// Returns: { "sum": 3 }
        /// </summary>
        private Dictionary<string, object> ExecuteAdd(Dictionary<string, object> args)
        {
            if (args == null || !args.ContainsKey("a") || !args.ContainsKey("b"))
            {
                throw new ArgumentException("Add requires 'a' and 'b' arguments");
            }

            var a = Convert.ToDouble(args["a"]);
            var b = Convert.ToDouble(args["b"]);

            return new Dictionary<string, object>
            {
                ["sum"] = a + b
            };
        }

        /// <summary>
        /// Sleep task - sleeps for a given number of milliseconds.
        /// Args: { "ms": 1000 }
        /// Returns: { "slept_ms": 1000 }
        /// </summary>
        private Dictionary<string, object> ExecuteSleep(Dictionary<string, object> args)
        {
            var ms = 100; // default
            if (args != null && args.ContainsKey("ms"))
            {
                ms = Convert.ToInt32(args["ms"]);
            }

            Thread.Sleep(ms);

            return new Dictionary<string, object>
            {
                ["slept_ms"] = ms
            };
        }

        /// <summary>
        /// Fail task - always throws an exception.
        /// Args: { "message": "custom error" } (optional)
        /// </summary>
        private Dictionary<string, object> ExecuteFail(Dictionary<string, object> args)
        {
            var message = args != null && args.ContainsKey("message")
                ? args["message"]?.ToString()
                : "Intentional failure for testing";

            throw new InvalidOperationException(message);
        }

        /// <summary>
        /// Get state task - returns the current state dictionary.
        /// Args: none
        /// Returns: { "state": { ... } }
        /// </summary>
        private Dictionary<string, object> ExecuteGetState(Dictionary<string, object> args)
        {
            return new Dictionary<string, object>
            {
                ["state"] = new Dictionary<string, object>(_state)
            };
        }

        /// <summary>
        /// Set state task - sets a key in the state dictionary.
        /// Args: { "key": "mykey", "value": "myvalue" }
        /// Returns: { "key": "mykey", "value": "myvalue" }
        /// </summary>
        private Dictionary<string, object> ExecuteSetState(Dictionary<string, object> args)
        {
            if (args == null || !args.ContainsKey("key"))
            {
                throw new ArgumentException("SetState requires 'key' argument");
            }

            var key = args["key"].ToString();
            var value = args.ContainsKey("value") ? args["value"] : null;

            _state[key] = value;

            return new Dictionary<string, object>
            {
                ["key"] = key,
                ["value"] = value
            };
        }

        /// <summary>
        /// Slow operation task - simulates a long-running operation.
        /// Uses loop + sleep to simulate a long operation (not just one big sleep).
        /// This is more realistic and tests timeout behavior better.
        /// Args: { "iterations": 100 } (optional, default 100)
        /// Returns: { "completed_iterations": 100, "slept_ms": 10000 }
        /// </summary>
        private Dictionary<string, object> ExecuteSlowOperation(Dictionary<string, object> args)
        {
            int iterations = 100;
            if (args != null && args.ContainsKey("iterations"))
            {
                iterations = Convert.ToInt32(args["iterations"]);
            }

            for (int i = 0; i < iterations; i++)
            {
                Thread.Sleep(100);  // 100ms per iteration = ~10 seconds total for 100 iterations
            }

            return new Dictionary<string, object>
            {
                ["completed_iterations"] = iterations,
                ["slept_ms"] = iterations * 100
            };
        }

        /// <summary>
        /// Large output task - writes a large volume of text to stdout.
        /// Tests that stdout buffer doesn't block the process when not being read.
        /// Args: { "lines": 1000, "chars_per_line": 10 } (optional, defaults to 1000 lines of 10 chars = 10k chars)
        /// Returns: { "lines_written": 1000, "total_chars": 10000 }
        /// </summary>
        private Dictionary<string, object> ExecuteLargeOutput(Dictionary<string, object> args)
        {
            int lines = 1000;
            int charsPerLine = 10;

            if (args != null)
            {
                if (args.ContainsKey("lines"))
                {
                    lines = Convert.ToInt32(args["lines"]);
                }
                if (args.ContainsKey("chars_per_line"))
                {
                    charsPerLine = Convert.ToInt32(args["chars_per_line"]);
                }
            }

            // Generate line content (repeating 'X' characters)
            string lineContent = new string('X', charsPerLine);

            // Write to stdout
            for (int i = 0; i < lines; i++)
            {
                Console.WriteLine(lineContent);
            }

            return new Dictionary<string, object>
            {
                ["lines_written"] = lines,
                ["total_chars"] = lines * (charsPerLine + Environment.NewLine.Length)
            };
        }

        /// <summary>
        /// Output then hang task - writes lines to stdout, then enters an infinite loop.
        /// Used to test that stdout output is captured in diagnostics when a task times out.
        /// Args: { "lines": 100 } (optional, defaults to 100 lines)
        /// Never returns (hangs forever).
        /// </summary>
        private Dictionary<string, object> ExecuteOutputThenHang(Dictionary<string, object> args)
        {
            int lines = 100;

            if (args != null && args.ContainsKey("lines"))
            {
                lines = Convert.ToInt32(args["lines"]);
            }

            // Write numbered lines to stdout for easy verification
            for (int i = 1; i <= lines; i++)
            {
                Console.WriteLine($"[OUTPUT_THEN_HANG] Line {i} of {lines}");
            }
            Console.Out.Flush();

            // Enter infinite loop (will cause timeout)
            while (true)
            {
                Thread.Sleep(100);
            }

            // Never reached, but required for compilation
            #pragma warning disable CS0162 // Unreachable code detected
            return new Dictionary<string, object>();
            #pragma warning restore CS0162
        }
    }
}

