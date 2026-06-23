using System.Collections.Generic;

namespace CosmonSWService
{
    /// <summary>
    /// Interface for task routing.
    ///
    /// The router is responsible for:
    /// 1. Pre-task validation (pre_task_check)
    /// 2. Task execution (execute_task)
    ///
    /// Any state (like global application state) should be stored as
    /// instance variables in the implementing class.
    /// </summary>
    public interface ITaskRouter
    {
        /// <summary>
        /// Called before executing a task.
        /// Use this to validate preconditions (e.g., is the app connected?).
        /// </summary>
        /// <param name="preTaskCheckArgs">Optional arguments for pre-task validation (may be null).</param>
        /// <returns>
        /// TaskCheckResult indicating whether to proceed with the task.
        /// </returns>
        TaskCheckResult PreTaskCheck(Dictionary<string, object> preTaskCheckArgs);

        /// <summary>
        /// Execute a task by name with the given arguments.
        /// </summary>
        /// <param name="taskName">Name of the task to execute.</param>
        /// <param name="taskArgs">Arguments for the task (may be null).</param>
        /// <returns>
        /// Dictionary containing the task result.
        /// </returns>
        Dictionary<string, object> ExecuteTask(string taskName, Dictionary<string, object> taskArgs);

        /// <summary>
        /// Get a list of available task names.
        /// Useful for health checks and debugging.
        /// </summary>
        IEnumerable<string> GetAvailableTasks();
    }

    /// <summary>
    /// Result of a pre-task check. A failure surfaces to Python as a
    /// "ReportedError" with the message as the only structured signal.
    /// </summary>
    public class TaskCheckResult
    {
        public bool CanProceed { get; set; }
        public string ErrorMessage { get; set; }

        public static TaskCheckResult Success()
        {
            return new TaskCheckResult { CanProceed = true };
        }

        public static TaskCheckResult Failure(string message)
        {
            return new TaskCheckResult
            {
                CanProceed = false,
                ErrorMessage = message
            };
        }
    }
}
