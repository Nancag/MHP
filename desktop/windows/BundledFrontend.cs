using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;

namespace MhpClient {
    // Frontend files are read from the EXE resource, never from the remote homepage.
    // Keeping the existing HTTPS origin preserves HttpOnly/SameSite authentication.
    internal sealed class BundledFrontend : IDisposable {
        private readonly Stream source;
        private readonly ZipArchive archive;
        private readonly Dictionary<string, ZipArchiveEntry> entries;
        internal BundledFrontend() {
            source = Assembly.GetExecutingAssembly().GetManifestResourceStream("MHP.Frontend.zip");
            if (source == null) throw new InvalidDataException("客户端页面资源缺失");
            archive = new ZipArchive(source, ZipArchiveMode.Read, false);
            entries = new Dictionary<string, ZipArchiveEntry>(StringComparer.Ordinal);
            long total = 0;
            foreach (var entry in archive.Entries) {
                string name = entry.FullName;
                if (name != "index.html" && !name.StartsWith("assets/", StringComparison.Ordinal)) throw new InvalidDataException("页面资源路径无效");
                if (name.Split('/').Any(p => p == ".." || p == "." || p.Length == 0) || name.Contains("\\") || entries.ContainsKey(name)) throw new InvalidDataException("页面资源路径无效");
                total += entry.Length;
                if (entry.Length > 20 * 1024 * 1024 || total > 100 * 1024 * 1024 || entries.Count >= 1024) throw new InvalidDataException("页面资源过大");
                entries.Add(name, entry);
            }
            if (!entries.ContainsKey("index.html")) throw new InvalidDataException("客户端首页缺失");
        }
        internal static bool IsApi(Uri uri) {
            return uri.AbsolutePath.StartsWith("/api/", StringComparison.Ordinal);
        }
        internal byte[] Read(Uri uri, string method, out string mime) {
            mime = "text/plain; charset=utf-8";
            if (method != "GET" && method != "HEAD") return null;
            string path = Uri.UnescapeDataString(uri.AbsolutePath);
            if (path.Contains("\\") || path.Contains("\0") || path.Split('/').Any(p => p == "." || p == "..")) return null;
            string name = path == "/" || path == "/index.html" ? "index.html" : path.TrimStart('/');
            ZipArchiveEntry entry;
            if (!entries.TryGetValue(name, out entry)) return null;
            switch (Path.GetExtension(name).ToLowerInvariant()) {
                case ".html": mime = "text/html; charset=utf-8"; break;
                case ".js": mime = "text/javascript; charset=utf-8"; break;
                case ".css": mime = "text/css; charset=utf-8"; break;
                case ".png": mime = "image/png"; break;
                case ".jpg": case ".jpeg": mime = "image/jpeg"; break;
                case ".webp": mime = "image/webp"; break;
                case ".svg": mime = "image/svg+xml"; break;
                case ".woff2": mime = "font/woff2"; break;
                case ".woff": mime = "font/woff"; break;
                default: mime = "application/octet-stream"; break;
            }
            if (method == "HEAD") return new byte[0];
            using (var input = entry.Open()) using (var output = new MemoryStream()) {
                input.CopyTo(output);
                return output.ToArray();
            }
        }
        public void Dispose() { archive.Dispose(); }
    }
}
