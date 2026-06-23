using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;

namespace CosmonSWService
{
    /// <summary>
    /// JSON protocol for named pipe communication.
    /// Handles serialization/deserialization of requests and responses.
    /// </summary>
    public static class Protocol
    {
        // Built-in request types (handled by PipeServer directly)
        public const string REQUEST_SHUTDOWN = "shutdown";

        // Response statuses
        public const string STATUS_SUCCESS = "success";
        public const string STATUS_ERROR = "error";

        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer
        {
            MaxJsonLength = int.MaxValue
        };

        /// <summary>
        /// Parse a JSON request string into a ServiceRequest object.
        /// </summary>
        public static ServiceRequest ParseRequest(string json)
        {
            try
            {
                var dict = Serializer.Deserialize<Dictionary<string, object>>(json);
                if (dict == null)
                    return null;

                return new ServiceRequest
                {
                    RequestId = dict.ContainsKey("request_id") ? dict["request_id"]?.ToString() : null,
                    RequestType = dict.ContainsKey("request_type") ? dict["request_type"]?.ToString() : null,
                    Args = dict.ContainsKey("args") ? dict["args"] as Dictionary<string, object> : null,
                    PreTaskCheckArgs = dict.ContainsKey("pre_task_check_args") 
                        ? dict["pre_task_check_args"] as Dictionary<string, object> 
                        : null
                };
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[ERROR] Failed to parse request: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Serialize a ServiceResponse to JSON string.
        /// </summary>
        public static string SerializeResponse(ServiceResponse response)
        {
            var dict = new Dictionary<string, object>
            {
                ["request_id"] = response.RequestId,
                ["status"] = response.Status
            };

            if (response.Status == STATUS_SUCCESS)
            {
                if (response.Result != null)
                    dict["result"] = response.Result;
            }
            else
            {
                dict["error_type"] = response.ErrorType ?? "UnknownError";
                dict["error_message"] = response.ErrorMessage ?? "Unknown error occurred";
            }

            return Serializer.Serialize(dict);
        }

        /// <summary>
        /// Create a success response with optional result data.
        /// </summary>
        public static ServiceResponse SuccessResponse(string requestId, Dictionary<string, object> result = null)
        {
            return new ServiceResponse
            {
                RequestId = requestId,
                Status = STATUS_SUCCESS,
                Result = result
            };
        }

        /// <summary>
        /// Create an error response.
        /// </summary>
        public static ServiceResponse ErrorResponse(string requestId, string errorType, string message)
        {
            return new ServiceResponse
            {
                RequestId = requestId,
                Status = STATUS_ERROR,
                ErrorType = errorType,
                ErrorMessage = message
            };
        }

        /// <summary>
        /// Build a result dict for an expected, user-actionable error
        /// condition (no active document, document not found, etc.).
        /// Python turns this into a ReportedExecutionError shown to the user.
        /// </summary>
        public static Dictionary<string, object> ReportedErrorResult(string message)
        {
            return new Dictionary<string, object>
            {
                ["status"] = STATUS_ERROR,
                ["error_type"] = "ReportedError",
                ["message"] = message
            };
        }
    }

    /// <summary>
    /// Parsed request from the pipe.
    /// </summary>
    public class ServiceRequest
    {
        public string RequestId { get; set; }
        public string RequestType { get; set; }
        public Dictionary<string, object> Args { get; set; }

        /// <summary>
        /// Optional arguments for pre-task validation.
        /// Use this to pass context that PreTaskCheck needs to validate.
        /// </summary>
        public Dictionary<string, object> PreTaskCheckArgs { get; set; }
    }

    /// <summary>
    /// Response to send back over the pipe.
    /// </summary>
    public class ServiceResponse
    {
        public string RequestId { get; set; }
        public string Status { get; set; }

        // Success field
        public Dictionary<string, object> Result { get; set; }

        // Error fields
        public string ErrorType { get; set; }
        public string ErrorMessage { get; set; }
    }
}
