/* Shared lazy history loader. Content-addressed buckets remain valid across builds. */
(() => {
  const pending = new Map();
  function json(url) {
    if (!pending.has(url)) {
      const request = fetch(url, { cache: 'no-cache' }).then(response => {
        if (!response.ok) {
          const error = new Error('Could not load rank history.');
          error.status = response.status;
          throw error;
        }
        return response.json();
      }).catch(error => { pending.delete(url); throw error; });
      pending.set(url, request);
    }
    return pending.get(url);
  }
  function bucketFor(key, count) {
    let value = 2166136261;
    for (const byte of new TextEncoder().encode(key)) value = Math.imul(value ^ byte, 16777619) >>> 0;
    return value % count;
  }
  async function load(dataset, key) {
    let manifest;
    try { manifest = await json(`data/${dataset}.manifest.json`); }
    catch (error) {
      if (error.status !== 404) throw error;
      return json(`data/${dataset}.json`); // compatibility while producers deploy
    }
    if (manifest.version !== 1 || manifest.bucket_count !== 64 || manifest.buckets.length !== 64)
      throw new Error('Unsupported rank history format.');
    return json(manifest.buckets[bucketFor(key, manifest.bucket_count)]);
  }
  window.PlayerHistory = { load, bucketFor };
})();
