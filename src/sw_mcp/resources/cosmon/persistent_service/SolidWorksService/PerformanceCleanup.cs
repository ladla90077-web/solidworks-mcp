using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

namespace CosmonSWService
{
    /// <summary>
    /// Utility class for resetting SolidWorks performance optimization flags.
    ///
    /// This is designed to be run after non-graceful shutdown of the main service
    /// to ensure SolidWorks is not left in a degraded state with:
    /// - Graphics updates disabled
    /// - Feature tree updates disabled
    /// - CommandInProgress flag set
    /// - Window input disabled (EnableWindow=false)
    /// </summary>
    public static class PerformanceCleanup
    {
        // Win32 API for window manipulation
        [DllImport("user32.dll")]
        private static extern bool EnableWindow(IntPtr hWnd, bool bEnable);

        [DllImport("user32.dll")]
        private static extern bool IsWindowEnabled(IntPtr hWnd);

        /// <summary>
        /// Exit codes for the cleanup tool.
        /// </summary>
        public static class ExitCodes
        {
            /// <summary>Success - flags reset or no SolidWorks/document to reset.</summary>
            public const int Success = 0;
            
            /// <summary>Failed to connect to SolidWorks (but it might not be running).</summary>
            public const int NoSolidWorks = 1;
            
            /// <summary>Error during cleanup (but best-effort reset was attempted).</summary>
            public const int Error = 2;
        }

        /// <summary>
        /// Run the full cleanup process. Returns an exit code.
        /// </summary>
        public static int Run()
        {
            ISldWorks swApp = null;
            
            try
            {
                // Connect to running SolidWorks instance
                swApp = ConnectToSolidWorks();
                if (swApp == null)
                {
                    return ExitCodes.Success;  // Not an error - SW might not be running
                }

                // Re-enable window FIRST (in case it was disabled by nuclear lock)
                ReEnableWindow(swApp);

                // Reset global CommandInProgress flag
                ResetCommandInProgress(swApp);

                // Reset document-level flags if there's an active document
                ResetDocumentFlags(swApp);

                return ExitCodes.Success;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[CosmonSWCleanup] Error during cleanup: {ex.Message}");
                
                // Try best-effort reset even on error
                if (swApp != null)
                {
                    try
                    {
                        // Re-enable window first
                        ReEnableWindow(swApp);
                        swApp.CommandInProgress = false;
                    }
                    catch
                    {
                        // Ignore - we're already handling an error
                    }
                }
                
                return ExitCodes.Error;
            }
            finally
            {
                // Release COM reference (don't close SolidWorks, just release)
                if (swApp != null)
                {
                    try
                    {
                        Marshal.ReleaseComObject(swApp);
                    }
                    catch
                    {
                        // Ignore cleanup errors
                    }
                }
            }
        }

        /// <summary>
        /// Connect to a running SolidWorks instance via the compile-time ROT moniker.
        /// Returns null if the moniker is not found in the ROT.
        /// </summary>
        private static ISldWorks ConnectToSolidWorks()
        {
            return RotHelper.ConnectViaROT(CompileTimeConfig.RotMoniker);
        }

        /// <summary>
        /// Re-enable the SolidWorks window if it was disabled by the nuclear lock.
        /// </summary>
        private static void ReEnableWindow(ISldWorks swApp)
        {
            try
            {
                IFrame swFrame = swApp.Frame() as IFrame;
                if (swFrame != null)
                {
                    long hwnd = swFrame.GetHWndx64();
                    IntPtr windowHandle = new IntPtr(hwnd);
                    
                    // Check if window is disabled and re-enable it
                    if (!IsWindowEnabled(windowHandle))
                    {
                        EnableWindow(windowHandle, true);
                        Console.WriteLine("[CosmonSWCleanup] Re-enabled SolidWorks window (was disabled by nuclear lock)");
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[CosmonSWCleanup] Warning: Could not check/reset window state: {ex.Message}");
                // Continue with other cleanup
            }
        }

        /// <summary>
        /// Reset the global CommandInProgress flag.
        /// </summary>
        private static void ResetCommandInProgress(ISldWorks swApp)
        {
            try
            {
                // Always set to false regardless of current state
                swApp.CommandInProgress = false;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[CosmonSWCleanup] Warning: Could not reset CommandInProgress: {ex.Message}");
                // Continue with other cleanup
            }
        }

        /// <summary>
        /// Reset document-level performance flags (graphics updates, feature tree).
        /// </summary>
        private static void ResetDocumentFlags(ISldWorks swApp)
        {
            try
            {
                ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;
                if (doc == null)
                {
                    return;
                }

                // Reset graphics updates
                IModelView modelView = doc.ActiveView as IModelView;
                if (modelView != null)
                {
                    try
                    {
                        modelView.EnableGraphicsUpdate = true;
                    }
                    catch (Exception ex)
                    {
                        Console.Error.WriteLine($"[CosmonSWCleanup] Warning: Could not reset EnableGraphicsUpdate: {ex.Message}");
                    }
                }

                // Reset feature tree updates
                IFeatureManager featureManager = doc.FeatureManager as IFeatureManager;
                if (featureManager != null)
                {
                    try
                    {
                        featureManager.EnableFeatureTree = true;
                    }
                    catch (Exception ex)
                    {
                        Console.Error.WriteLine($"[CosmonSWCleanup] Warning: Could not reset EnableFeatureTree: {ex.Message}");
                    }
                }

                // Force a redraw to ensure changes take effect
                try
                {
                    doc.GraphicsRedraw2();
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[CosmonSWCleanup] Warning: Could not force redraw: {ex.Message}");
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[CosmonSWCleanup] Warning: Error during document flag reset: {ex.Message}");
                // Not a fatal error - CommandInProgress was already reset
            }
        }
    }
}

