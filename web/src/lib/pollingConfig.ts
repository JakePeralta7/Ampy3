/**
 * Centralized polling configuration for all data-fetching hooks
 */

export const POLLING_CONFIG = {
  // Default interval for most pages
  DEFAULT_INTERVAL: 30000, // 30 seconds

  // Fast polling after manual user action (e.g., sync trigger)
  FAST_INTERVAL: 3000, // 3 seconds

  // Interval for retrying failed requests
  RETRY_INTERVAL: 5000, // 5 seconds

  // Maximum number of retry attempts before giving up
  MAX_RETRIES: 3,

  // Adaptive polling for pipeline monitoring
  PIPELINE_RUNNING_INTERVAL: 2000, // 2 seconds while pipeline is active
  PIPELINE_IDLE_INTERVAL: 10000, // 10 seconds when idle

  // Task polling (e.g., playlist detail matching)
  TASK_POLL_INTERVAL: 500, // 500ms for quick feedback
  TASK_MAX_RETRIES: 20,

  // Explore content caching
  EXPLORE_CACHE_TTL: 60000, // 1 minute

  // Source playlist caching
  SOURCE_PLAYLIST_CACHE_TTL: 60000, // 1 minute
};

/**
 * Backoff strategy for failed requests
 * Returns the delay (ms) before the nth retry
 */
export function getRetryDelay(attemptNumber: number): number {
  // Exponential backoff: 5s, 10s, 20s, 30s (capped at MAX_RETRY_DELAY)
  const exponential = POLLING_CONFIG.RETRY_INTERVAL * Math.pow(2, attemptNumber - 1);
  return Math.min(exponential, POLLING_CONFIG.RETRY_INTERVAL * 6); // 30s max
}

/**
 * Interval selector for adaptive polling scenarios
 */
export function getAdaptivePollingInterval(isActive: boolean): number {
  return isActive
    ? POLLING_CONFIG.PIPELINE_RUNNING_INTERVAL
    : POLLING_CONFIG.PIPELINE_IDLE_INTERVAL;
}
