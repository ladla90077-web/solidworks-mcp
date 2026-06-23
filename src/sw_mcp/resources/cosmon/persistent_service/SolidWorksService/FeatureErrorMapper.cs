using System.Collections.Generic;
using SolidWorks.Interop.swconst;

namespace CosmonSWService
{
    /// <summary>
    /// Maps swFeatureError_e error codes to human-readable descriptions.
    /// Used to annotate features in the feature tree with error/warning info.
    /// </summary>
    public static class FeatureErrorMapper
    {
        private static readonly Dictionary<int, string> ErrorDescriptions = new Dictionary<int, string>
        {
            // No error
            { 0, "No error" },

            // Unknown
            { 1, "Unknown error" },

            // Fillet/Chamfer errors (10-19)
            { 10, "Loop for fillet/chamfer does not exist" },
            { 11, "Face for fillet/chamfer does not exist" },
            { 12, "Invalid fillet radius or a face blend fillet recommended" },
            { 13, "Edge for fillet/chamfer does not exist" },
            { 14, "Failed to create fillet due to model geometry" },
            { 15, "Fillet radius too small" },
            { 16, "Selected elements cannot be extended to intersect" },
            { 17, "Specified radius would eliminate one of the elements" },
            { 18, "Radius is too big or elements are tangent or nearly tangent" },
            { 19, "Not used" },

            // Extrusion errors (30-37)
            { 30, "Feature would create a disjoint body; direction may be wrong" },
            { 31, "Cannot locate end of feature" },
            { 32, "Unable to create this extruded feature due to geometric conditions" },
            { 33, "Extruded cuts cannot have both open and closed contours" },
            { 34, "Extruded cuts require at least one closed or open contour that does not self-intersect" },
            { 35, "Open extruded cuts require a single open contour that does not self-intersect" },
            { 36, "Bosses cannot have both open and closed contours" },
            { 37, "Bosses require one or more closed contours that do not self-intersect" },

            // Mate errors (38-48)
            { 38, "One of the edges of this mate is suppressed, invalid, or no longer present" },
            { 39, "One of the faces of this mate is suppressed, invalid, or no longer present" },
            { 40, "Mating surface type is not supported" },
            { 41, "One of the entities of this mate is suppressed, invalid, or no longer present" },
            { 42, "Tangent not satisfied" },
            { 43, "Mate points to dangling geometry" },
            { 44, "Non-linear edges cannot be used for mating" },
            { 45, "Mating is not supported for one of the components or one of the components cannot currently be modified" },
            { 46, "This mate is over-defining the assembly; consider deleting some of the over-defining mates" },
            { 47, "This mate cannot be solved" },
            { 48, "One or more mate entities were suppressed" },

            // Sketch error
            { 51, "Sketch error" },

            // Partial edge fillet errors (52-68)
            { 52, "No intersection between reference entity and fillet edge" },
            { 53, "Failed to update the partial edge data" },
            { 54, "Failed to find propagate edges" },
            { 55, "Failed to find a start edge" },
            { 56, "Failed to find end edge" },
            { 57, "Failed to find the fillet/chamfer edge" },
            { 58, "The fillet offset is too large" },
            { 59, "Select a sketch point, reference point, reference plane, or planar face" },
            { 60, "Too many reference entities selected" },
            { 61, "Total offset from start point and end point must be less than 100%" },
            { 62, "End points cross over and result in a zero thickness fillet" },
            { 63, "Reference entity is missing" },
            { 64, "Reference entity is invalid" },
            { 65, "Partial edge fillet is not supported" },
            { 66, "Some edges form closed loops; partial edge fillet does not support closed loops" },
            { 67, "Failed to find a unique point for projection of reference offset" },
            { 68, "There are no references to repair" },

            // Codes 49, 50, 69, 70, 71, 72 have no description in the docs.
            // They fall through to the enum name fallback in GetErrorDescription().
        };

        /// <summary>
        /// Get a human-readable description for a swFeatureError_e error code.
        /// Falls back to the enum name, then to a generic message with the code number.
        /// </summary>
        public static string GetErrorDescription(int errorCode)
        {
            if (ErrorDescriptions.TryGetValue(errorCode, out string description))
                return description;

            // Try to get the enum member name as a fallback
            string enumName = System.Enum.GetName(typeof(swFeatureError_e), errorCode);
            if (enumName != null)
                return enumName;

            return $"Unknown error (code {errorCode})";
        }
    }
}
