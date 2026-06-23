using System;
using System.IO;
using System.Threading;

namespace CosmonSWService
{
    /// <summary>
    /// TEST ONLY. Cross-process probe used to measure observed parallelism
    /// of operations protected (or not protected) by the per-session
    /// serialization lock.
    ///
    /// Two on-disk files share state across all concurrent probe callers:
    ///   - currentPath: number of probes currently inside the sleep window.
    ///   - maxPath:     high-water mark of currentPath ever observed.
    ///
    /// A system-wide named mutex (Global\NexusSerializeProbe) protects the
    /// read/increment/max-update and the read/decrement so the probe itself
    /// never races. The only thing that determines maxPath is whether the
    /// probes overlap during the sleep window:
    ///   serialized   -> maxPath == 1
    ///   unserialized -> maxPath approaches N for N concurrent callers.
    /// </summary>
    internal static class ParallelismProbeHelper
    {
        public const string MUTEX_NAME = @"Global\NexusSerializeProbe";

        public static void RunProbe(string currentPath, string maxPath, int sleepMs)
        {
            using (var mutex = new Mutex(initiallyOwned: false, name: MUTEX_NAME))
            {
                BumpUp(mutex, currentPath, maxPath);
                Thread.Sleep(sleepMs);
                BumpDown(mutex, currentPath);
            }
        }

        private static void BumpUp(Mutex mutex, string currentPath, string maxPath)
        {
            mutex.WaitOne();
            try
            {
                int current = ReadIntOrZero(currentPath) + 1;
                WriteInt(currentPath, current);

                int max = ReadIntOrZero(maxPath);
                if (current > max)
                    WriteInt(maxPath, current);
            }
            finally
            {
                mutex.ReleaseMutex();
            }
        }

        private static void BumpDown(Mutex mutex, string currentPath)
        {
            mutex.WaitOne();
            try
            {
                int current = ReadIntOrZero(currentPath) - 1;
                WriteInt(currentPath, current);
            }
            finally
            {
                mutex.ReleaseMutex();
            }
        }

        private static int ReadIntOrZero(string path)
        {
            if (!File.Exists(path))
                return 0;
            string text = File.ReadAllText(path).Trim();
            if (text.Length == 0)
                return 0;
            return int.Parse(text);
        }

        private static void WriteInt(string path, int value)
        {
            File.WriteAllText(path, value.ToString());
        }
    }
}
