using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

namespace CosmonSWService
{
    /// <summary>
    /// Win32 API helpers for window manipulation.
    /// </summary>
    internal static class Win32Helpers
    {
        [DllImport("user32.dll")]
        public static extern bool EnableWindow(IntPtr hWnd, bool bEnable);

        [DllImport("user32.dll")]
        public static extern bool IsWindowEnabled(IntPtr hWnd);
    }

    /// <summary>
    /// Result of checking SolidWorks performance flags.
    /// </summary>
    internal class PerformanceFlagsStatus
    {
        public bool CommandInProgress { get; set; }
        public bool WindowEnabled { get; set; }
        public bool HasActiveDocument { get; set; }
        public bool? GraphicsUpdateEnabled { get; set; }
        public bool? FeatureTreeEnabled { get; set; }
    }

    /// <summary>
    /// Static helper methods for setting/resetting SolidWorks performance flags.
    /// Used by PerformanceOptimizationScope and test code.
    /// </summary>
    internal static class PerformanceFlagsHelper
    {
        /// <summary>
        /// Checks the current state of all performance-related flags.
        /// </summary>
        public static PerformanceFlagsStatus CheckFlags(ISldWorks swApp)
        {
            var status = new PerformanceFlagsStatus();

            // Check global CommandInProgress flag
            status.CommandInProgress = swApp.CommandInProgress;

            // Check window enabled state (nuclear lock via Win32 API)
            IFrame swFrame = swApp.Frame() as IFrame;
            if (swFrame == null)
            {
                throw new InvalidOperationException("Failed to get SolidWorks frame for window state check");
            }
            long hwnd = swFrame.GetHWndx64();
            status.WindowEnabled = Win32Helpers.IsWindowEnabled(new IntPtr(hwnd));

            // Check document-level flags (if document is open)
            IModelDoc2 doc = swApp.ActiveDoc as IModelDoc2;
            if (doc != null)
            {
                status.HasActiveDocument = true;

                IModelView modelView = doc.ActiveView as IModelView;
                status.GraphicsUpdateEnabled = modelView?.EnableGraphicsUpdate;

                IFeatureManager featureManager = doc.FeatureManager as IFeatureManager;
                status.FeatureTreeEnabled = featureManager?.EnableFeatureTree;
            }
            else
            {
                status.HasActiveDocument = false;
                status.GraphicsUpdateEnabled = null;
                status.FeatureTreeEnabled = null;
            }

            return status;
        }

        /// <summary>
        /// Disables all performance-related flags on SolidWorks.
        /// Returns the window handle that was disabled (or IntPtr.Zero if not available).
        /// </summary>
        public static IntPtr DisableFlags(ISldWorks swApp, IModelDoc2 doc)
        {
            IntPtr windowHandle = IntPtr.Zero;

            // Set global flag
            swApp.CommandInProgress = true;

            // Set document-level flags if document is open
            if (doc != null)
            {
                IModelView modelView = doc.ActiveView as IModelView;
                if (modelView != null)
                    modelView.EnableGraphicsUpdate = false;

                IFeatureManager featureManager = doc.FeatureManager as IFeatureManager;
                if (featureManager != null)
                    featureManager.EnableFeatureTree = false;
            }

            // NUCLEAR: Disable window via Win32 API
            try
            {
                IFrame swFrame = swApp.Frame() as IFrame;
                if (swFrame != null)
                {
                    long hwnd = swFrame.GetHWndx64();
                    windowHandle = new IntPtr(hwnd);
                    Win32Helpers.EnableWindow(windowHandle, false);
                }
            }
            catch
            {
                // Non-fatal - continue without window disabling
                windowHandle = IntPtr.Zero;
            }

            return windowHandle;
        }

        /// <summary>
        /// Re-enables all performance-related flags on SolidWorks.
        /// </summary>
        public static void EnableFlags(ISldWorks swApp, IModelView modelView, IFeatureManager featureManager, IntPtr windowHandle)
        {
            try
            {
                // NUCLEAR REVERSAL: Re-enable window FIRST to restore user input
                if (windowHandle != IntPtr.Zero)
                {
                    Win32Helpers.EnableWindow(windowHandle, true);
                }

                // Re-enable all updates in reverse order
                if (swApp != null)
                    swApp.CommandInProgress = false;

                if (modelView != null)
                    modelView.EnableGraphicsUpdate = true;

                if (featureManager != null)
                    featureManager.EnableFeatureTree = true;
            }
            catch
            {
                // Suppress exceptions during cleanup
            }
        }
    }

    /// <summary>
    /// Disables graphics updates, feature tree updates, UI rendering, and user input 
    /// during SolidWorks API operations.
    /// This provides massive speedup (10-20x) for bulk operations like feature tree walking
    /// and prevents user interference during API operations.
    /// 
    /// Optimizations applied:
    /// - CommandInProgress = true: Suppresses all UI updates and background processes
    /// - EnableGraphicsUpdate = false: Stops graphics window redraws
    /// - EnableFeatureTree = false: Skips feature tree updates
    /// - EnableWindow = false: NUCLEAR - completely disables user input to prevent interference
    /// 
    /// Usage: Wrap API-heavy code in a using statement:
    ///     using (new PerformanceOptimizationScope(swApp, doc))
    ///     {
    ///         // Walk feature tree, iterate over features, etc.
    ///     }
    /// </summary>
    public sealed class PerformanceOptimizationScope : IDisposable
    {
        private readonly ISldWorks _swApp;
        private readonly IModelView _modelView;
        private readonly IFeatureManager _featureManager;
        private readonly IntPtr _windowHandle;
        private bool _disposed;

        public PerformanceOptimizationScope(ISldWorks swApp, IModelDoc2 doc)
        {
            _swApp = swApp ?? throw new ArgumentNullException(nameof(swApp));
            
            if (doc != null)
            {
                _modelView = doc.ActiveView as IModelView;
                _featureManager = doc.FeatureManager as IFeatureManager;

                // Use shared helper to disable all flags
                _windowHandle = PerformanceFlagsHelper.DisableFlags(swApp, doc);
            }
            else
            {
                _modelView = null;
                _featureManager = null;
                _windowHandle = IntPtr.Zero;
            }
        }

        public void Dispose()
        {
            if (_disposed)
                return;

            _disposed = true;

            // Use shared helper to re-enable all flags
            PerformanceFlagsHelper.EnableFlags(_swApp, _modelView, _featureManager, _windowHandle);
        }
    }
}

