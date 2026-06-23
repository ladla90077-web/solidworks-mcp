using System;
using System.IO;
using System.Reflection;

namespace CosmonSWService
{
    /// <summary>
    /// Entry point for the standalone cleanup tool (CosmonSWCleanup.exe).
    /// 
    /// This is built as a separate target from the main service, sharing all
    /// the same source files but with a different entry point.
    /// 
    /// Build with: msbuild /p:Configuration=Cleanup
    /// </summary>
    static class CleanupProgram
    {
        // Static constructor for assembly resolution - runs when class is first accessed
        // SolidWorks API path is baked in at compile time via CompileTimeConfig.cs
        static CleanupProgram()
        {
            AppDomain.CurrentDomain.AssemblyResolve += (sender, args) =>
            {
                string swPath = CompileTimeConfig.SolidWorksApiPath;
                string assemblyName = new AssemblyName(args.Name).Name;
                string assemblyPath = Path.Combine(swPath, assemblyName + ".dll");

                if (File.Exists(assemblyPath))
                {
                    return Assembly.LoadFrom(assemblyPath);
                }
                return null;
            };
        }

        static int Main(string[] args)
        {
            // Startup canary: Python checks for this line to detect antivirus interference.
            Console.WriteLine("COSMON_EXE_STARTED");
            Console.Out.Flush();

            return PerformanceCleanup.Run();
        }
    }
}

