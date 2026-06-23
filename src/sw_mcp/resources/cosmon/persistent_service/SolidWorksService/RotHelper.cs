using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using SolidWorks.Interop.sldworks;

namespace CosmonSWService
{
    /// <summary>
    /// Shared helper for connecting to SOLIDWORKS via the Running Object Table.
    /// Used by both <see cref="SolidWorksConnection"/> and <see cref="PerformanceCleanup"/>.
    /// </summary>
    static class RotHelper
    {
        [DllImport("ole32.dll")]
        private static extern int GetRunningObjectTable(int reserved, out IRunningObjectTable pprot);

        [DllImport("ole32.dll")]
        private static extern int CreateBindCtx(int reserved, out IBindCtx ppbc);

        /// <summary>
        /// Connect to SOLIDWORKS via the Running Object Table by matching a
        /// specific moniker display name (e.g. "SolidWorks_PID_12345").
        /// Returns null if the moniker is not found.
        /// </summary>
        public static ISldWorks ConnectViaROT(string targetMoniker)
        {
            IRunningObjectTable rot;
            if (GetRunningObjectTable(0, out rot) != 0)
                return null;

            IBindCtx ctx;
            if (CreateBindCtx(0, out ctx) != 0)
                return null;

            IEnumMoniker enumMoniker;
            rot.EnumRunning(out enumMoniker);
            enumMoniker.Reset();

            IMoniker[] monikers = new IMoniker[1];
            IntPtr fetched = IntPtr.Zero;
            while (enumMoniker.Next(1, monikers, fetched) == 0)
            {
                string displayName;
                monikers[0].GetDisplayName(ctx, null, out displayName);

                if (displayName == targetMoniker)
                {
                    object comObj;
                    rot.GetObject(monikers[0], out comObj);
                    return comObj as ISldWorks;
                }
            }

            return null;
        }
    }
}
