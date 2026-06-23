using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

namespace CosmonSWService
{
    /// <summary>
    /// Manages the COM connection to SolidWorks.
    ///
    /// Connects via the Running Object Table using a moniker like
    /// "SolidWorks_PID_12345" (baked in at compile time via CompileTimeConfig).
    /// This targets a specific SolidWorks process, which is essential when
    /// multiple versions are installed.
    /// </summary>
    public class SolidWorksConnection : IDisposable
    {
        private ISldWorks _swApp;
        private bool _disposed;

        /// <summary>
        /// Gets the SolidWorks application instance.
        /// </summary>
        public ISldWorks SwApp => _swApp;

        /// <summary>
        /// Gets whether the connection is active and SolidWorks is still responsive.
        /// This performs an actual COM call to verify the connection - use sparingly.
        /// </summary>
        public bool IsConnected
        {
            get
            {
                if (_swApp == null)
                    return false;

                try
                {
                    // Perform a lightweight COM call to verify SolidWorks is still alive
                    // RevisionNumber() is a simple method that doesn't require an open document
                    string revision = _swApp.RevisionNumber();
                    return true;
                }
                catch (COMException)
                {
                    // SolidWorks was closed or crashed - clean up the stale reference
                    Console.WriteLine("[WARN] SolidWorks connection lost (detected stale RCW)");
                    // Cleanup the stale connection
                    try
                    {
                        Marshal.ReleaseComObject(_swApp);
                    }
                    catch
                    {
                        // Ignore errors - the COM object is already dead
                    }
                    _swApp = null;
                    return false;
                }
            }
        }

        /// <summary>
        /// Quick check if we have a reference (does NOT verify connection is alive).
        /// Use this for fast checks where you'll handle COMException anyway.
        /// </summary>
        public bool HasReference => _swApp != null;

        /// <summary>
        /// Initialize the connection to SolidWorks via ROT moniker.
        ///
        /// Uses the ROT moniker baked in at compile time (CompileTimeConfig.RotMoniker)
        /// to connect to the specific SolidWorks process that Python detected.
        /// </summary>
        public void Connect()
        {
            if (_swApp != null)
            {
                Console.WriteLine("[DEBUG] SolidWorks already connected, skipping");
                return;
            }

            Console.WriteLine("[INFO] Connecting to SolidWorks...");
            Console.Out.Flush();

            // NOTE: Assembly resolver should be set up before this class is instantiated
            // (e.g., in SolidWorksRouter's static constructor)

            string rotMoniker = CompileTimeConfig.RotMoniker;

            Console.WriteLine($"[DEBUG] Connecting via ROT moniker '{rotMoniker}'...");
            Console.Out.Flush();

            _swApp = RotHelper.ConnectViaROT(rotMoniker);
            if (_swApp != null)
            {
                Console.WriteLine($"[INFO] Connected to SolidWorks via ROT moniker '{rotMoniker}'");
                Console.Out.Flush();
                return;
            }

            throw new InvalidOperationException(
                $"SOLIDWORKS ROT moniker '{rotMoniker}' not found in the Running Object Table. " +
                "The SOLIDWORKS process may have been restarted since detection. " +
                "Unexpected. Please re-try.");
        }

        /// <summary>
        /// Dispose the connection.
        /// </summary>
        public void Dispose()
        {
            if (_disposed)
                return;

            _disposed = true;

            if (_swApp != null)
            {
                try
                {
                    // Don't close SolidWorks, just release the reference
                    Marshal.ReleaseComObject(_swApp);
                }
                catch
                {
                    // Ignore errors during cleanup
                }
                _swApp = null;
            }
        }
    }
}
