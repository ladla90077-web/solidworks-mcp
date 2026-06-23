using System;
using System.Collections.Generic;
using System.Diagnostics;

namespace CosmonSWService
{
    /// <summary>
    /// Minimal Console-based profiler for operation timing.
    /// Logs start, intermediate marks, and completion with elapsed times.
    /// 
    /// Usage:
    ///   var prof = new SimpleProfiler("MyOperation");
    ///   prof.Mark("step 1");
    ///   prof.Mark("step 2");
    ///   prof.Done("success");
    /// </summary>
    public sealed class SimpleProfiler
    {
        private readonly string _name;
        private readonly Stopwatch _sw;
        private long _lastMs;

        public SimpleProfiler(string name)
        {
            _name = name ?? "profile";
            _sw = Stopwatch.StartNew();
            _lastMs = 0;
            Console.WriteLine($"[PROFILE] {_name} | start");
        }

        public void Mark(string label)
        {
            long now = _sw.ElapsedMilliseconds;
            long delta = now - _lastMs;
            _lastMs = now;
            Console.WriteLine($"[PROFILE] {_name} | +{delta}ms (t={now}ms) | {label}");
        }

        public void Done(string label = "done")
        {
            long total = _sw.ElapsedMilliseconds;
            Console.WriteLine($"[PROFILE] {_name} | total={total}ms | {label}");
        }

        /// <summary>
        /// Returns elapsed milliseconds since the profiler was created.
        /// </summary>
        public long ElapsedMs => _sw.ElapsedMilliseconds;
    }

    /// <summary>
    /// Generic named timing buckets for aggregating timings across loops/steps.
    /// Uses Stopwatch TICKS internally for sub-millisecond precision, then converts to ms at reporting time.
    /// 
    /// - AddTicks(name, ticks): accumulate external Stopwatch measurements in ticks
    /// - AddMs(name, ms): legacy interface (still works but loses precision)
    /// - Measure(name): IDisposable scope for timing a block
    /// - GetMs(name): retrieve total ms for a bucket (precise, from ticks)
    /// - GetCount(name): number of additions for a bucket
    /// </summary>
    public sealed class NamedTimers
    {
        private readonly Dictionary<string, long> _ticksByName = new Dictionary<string, long>();
        private readonly Dictionary<string, int> _countByName = new Dictionary<string, int>();

        /// <summary>
        /// Add elapsed ticks from a Stopwatch (use sw.ElapsedTicks for precision).
        /// </summary>
        public void AddTicks(string name, long ticks)
        {
            if (string.IsNullOrEmpty(name)) return;

            if (!_ticksByName.ContainsKey(name)) _ticksByName[name] = 0;
            _ticksByName[name] += ticks;

            if (!_countByName.ContainsKey(name)) _countByName[name] = 0;
            _countByName[name] += 1;
        }

        /// <summary>
        /// Legacy: Add milliseconds directly. Prefer AddTicks for precision.
        /// </summary>
        public void AddMs(string name, long ms)
        {
            // Convert ms to ticks for internal storage
            long ticks = ms * Stopwatch.Frequency / 1000;
            AddTicks(name, ticks);
        }

        /// <summary>
        /// Get total milliseconds for a bucket (computed from accumulated ticks).
        /// </summary>
        public double GetMsDouble(string name)
        {
            if (string.IsNullOrEmpty(name)) return 0;
            if (!_ticksByName.ContainsKey(name)) return 0;
            return (double)_ticksByName[name] * 1000.0 / Stopwatch.Frequency;
        }

        /// <summary>
        /// Get total milliseconds as integer (for backward compatibility in log formatting).
        /// </summary>
        public long GetMs(string name)
        {
            return (long)Math.Round(GetMsDouble(name));
        }

        public int GetCount(string name)
        {
            if (string.IsNullOrEmpty(name)) return 0;
            return _countByName.ContainsKey(name) ? _countByName[name] : 0;
        }

        public TimingScope Measure(string name)
        {
            return new TimingScope(this, name);
        }

        public sealed class TimingScope : IDisposable
        {
            private readonly NamedTimers _owner;
            private readonly string _name;
            private readonly Stopwatch _sw;
            private bool _done;

            public TimingScope(NamedTimers owner, string name)
            {
                _owner = owner;
                _name = name;
                _sw = Stopwatch.StartNew();
                _done = false;
            }

            public void Dispose()
            {
                if (_done) return;
                _done = true;
                _sw.Stop();
                _owner.AddTicks(_name, _sw.ElapsedTicks);
            }
        }
    }

    /// <summary>
    /// Tracks cumulative session statistics for model state retrieval.
    /// Used to compare timing across subsequent walks within a service session.
    /// 
    /// The key insight is that RCW (Runtime Callable Wrapper) reuse should make
    /// subsequent walks faster than the first one. This class tracks timing to
    /// verify that hypothesis.
    /// </summary>
    public sealed class SessionStats
    {
        private readonly object _lock = new object();
        private int _walkCount;
        private long _totalWalkTimeMs;
        private long _minWalkTimeMs = long.MaxValue;
        private long _maxWalkTimeMs = long.MinValue;
        private long _firstWalkTimeMs;
        private readonly List<long> _walkTimes = new List<long>();

        /// <summary>
        /// Record a tree walk with timing.
        /// </summary>
        public void RecordWalk(long elapsedMs)
        {
            lock (_lock)
            {
                _walkCount++;
                _totalWalkTimeMs += elapsedMs;
                _walkTimes.Add(elapsedMs);

                if (_walkCount == 1)
                    _firstWalkTimeMs = elapsedMs;

                if (elapsedMs < _minWalkTimeMs) _minWalkTimeMs = elapsedMs;
                if (elapsedMs > _maxWalkTimeMs) _maxWalkTimeMs = elapsedMs;
            }
        }

        /// <summary>
        /// Log a summary of session statistics to show RCW warmup benefit.
        /// </summary>
        public void LogSummary()
        {
            lock (_lock)
            {
                Console.WriteLine("[PROFILE] === Session Statistics ===");
                Console.WriteLine($"[PROFILE] walk_count={_walkCount}");

                if (_walkCount > 0)
                {
                    double avgMs = (double)_totalWalkTimeMs / _walkCount;
                    Console.WriteLine($"[PROFILE] walk_time: first={_firstWalkTimeMs}ms, min={_minWalkTimeMs}ms, max={_maxWalkTimeMs}ms, avg={avgMs:F1}ms, total={_totalWalkTimeMs}ms");

                    // Show recent walk times for trend analysis (expect first to be slow, rest fast)
                    if (_walkTimes.Count > 0)
                    {
                        int showCount = Math.Min(10, _walkTimes.Count);
                        var recentTimes = _walkTimes.GetRange(_walkTimes.Count - showCount, showCount);
                        Console.WriteLine($"[PROFILE] recent_walks (last {showCount}): [{string.Join(", ", recentTimes)}]ms");

                        // Calculate speedup ratio if we have more than one walk
                        if (_walkCount > 1 && _firstWalkTimeMs > 0)
                        {
                            double avgSubsequent = (double)(_totalWalkTimeMs - _firstWalkTimeMs) / (_walkCount - 1);
                            double speedup = _firstWalkTimeMs / avgSubsequent;
                            Console.WriteLine($"[PROFILE] RCW_benefit: first={_firstWalkTimeMs}ms, avg_subsequent={avgSubsequent:F1}ms, speedup={speedup:F1}x");
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Get the number of walks completed so far.
        /// </summary>
        public int WalkCount
        {
            get
            {
                lock (_lock)
                {
                    return _walkCount;
                }
            }
        }
    }
}

