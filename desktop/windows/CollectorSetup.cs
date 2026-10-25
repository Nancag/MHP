// No elevation, registry changes, downloads or automatic extension installation.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;

public static class CollectorPayload
{
    public static readonly string[] Names = { "manifest.json", "popup.html", "popup.css", "popup.js", "extractor.js", "bridge.js", "background.js", "README.md" };
    public static byte[] Bytes()
    {
        using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("MHP.Collector.zip"))
        using (MemoryStream output = new MemoryStream()) { input.CopyTo(output); return output.ToArray(); }
    }
    public static string Fingerprint()
    {
        using (SHA256 hash = SHA256.Create()) { return BitConverter.ToString(hash.ComputeHash(Bytes())).Replace("-", "").ToLowerInvariant().Substring(0, 12); }
    }
    public static void Extract(string target)
    {
        string root = Path.GetFullPath(target).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        using (MemoryStream data = new MemoryStream(Bytes()))
        using (ZipArchive archive = new ZipArchive(data, ZipArchiveMode.Read))
        {
            if (archive.Entries.Count != Names.Length || archive.Entries.Select(e => e.FullName).Distinct().Count() != Names.Length ||
                archive.Entries.Any(e => !Names.Contains(e.FullName) || e.Length > 1024 * 1024))
                throw new InvalidDataException("插件包内容无效。");
            // Validate every destination before creating anything. Never follow junctions.
            for (DirectoryInfo parent = new DirectoryInfo(root); parent != null; parent = parent.Parent)
                if (parent.Exists && (parent.Attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("安装路径包含目录链接，请取消。");
            int existing = 0;
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                string file = Path.GetFullPath(Path.Combine(root, entry.FullName));
                if (!file.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("插件包路径无效。");
                if (File.Exists(file))
                {
                    if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0) throw new IOException("插件文件包含链接，请取消。");
                    using (MemoryStream expected = new MemoryStream())
                    using (Stream input = entry.Open())
                    {
                        input.CopyTo(expected);
                        if (new FileInfo(file).Length != expected.Length || !File.ReadAllBytes(file).SequenceEqual(expected.ToArray()))
                            throw new IOException("目标文件已被修改，工具不会覆盖。请在 Edge 查看已有插件，或使用 ZIP 手动安装到新目录。");
                    }
                    existing++;
                }
            }
            if (existing == Names.Length) return;
            if (existing != 0) throw new IOException("目标目录中有未完成的安装，工具不会覆盖。请使用 ZIP 手动安装到新目录。");
            Directory.CreateDirectory(root);
            foreach (ZipArchiveEntry entry in archive.Entries)
                using (Stream source = entry.Open())
                using (FileStream destination = new FileStream(Path.Combine(root, entry.FullName), FileMode.CreateNew)) source.CopyTo(destination);
        }
    }
}

public class CollectorSetup : Form
{
    readonly string target = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MHP", "Collector", "0.3.0-" + CollectorPayload.Fingerprint(), "mhp-collector");
    readonly Label status = new Label();
    readonly Button save = new Button(), edge = new Button(), folder = new Button(), copy = new Button();
    public CollectorSetup()
    {
        Text = "MHP 商品采集助手 · 安装辅助"; ClientSize = new Size(680, 440);
        StartPosition = FormStartPosition.CenterScreen; Font = new Font("Microsoft YaHei UI", 10);
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        Label instructions = new Label { Left = 24, Top = 20, Width = 630, Height = 145, Text =
            "只需安装一次，之后在 Edge 工具栏点击插件采集。\n\n1. 保存插件文件（无需手动解压，无需管理员权限）。\n2. 打开 Edge 扩展管理页，手动开启“开发人员模式”。\n3. 点击“加载解压缩的扩展”，粘贴下方路径并确认。\n4. 返回 MKHP 刷新，检查“插件已安装并启用”。" };
        TextBox path = new TextBox { Left = 24, Top = 178, Width = 630, Height = 55, Multiline = true, ReadOnly = true, Text = target };
        status.SetBounds(24, 240, 630, 65); status.Text = "此工具不会修改注册表、关闭浏览器或自动安装扩展。\n插件文件需保留，删除后插件将无法工作。";
        save.Text = "1 保存插件文件"; edge.Text = "2 打开 Edge 管理页"; folder.Text = "打开插件文件夹"; copy.Text = "复制加载路径";
        Button[] buttons = { save, edge, folder, copy };
        for (int i = 0; i < buttons.Length; i++) { buttons[i].SetBounds(24 + (i % 2) * 322, 315 + (i / 2) * 48, 308, 38); Controls.Add(buttons[i]); }
        edge.Enabled = folder.Enabled = copy.Enabled = false;
        save.Click += delegate {
            if (!Allow("允许将插件文件保存到以下目录吗？用途：供 Edge 手动加载。\n不会覆盖已有文件，也不会访问网络。\n\n" + target)) return;
            try {
                CollectorPayload.Extract(target); save.Enabled = false; edge.Enabled = folder.Enabled = copy.Enabled = true;
                status.Text = "文件已保存。下一步打开 Edge 管理页，开启开发人员模式，点击加载解压缩的扩展。";
            } catch (IOException ex) {
                status.Text = ex.Message;
            } catch (Exception) { status.Text = "无法保存插件文件，请检查目录权限及磁盘空间。未自动重试。"; }
        };
        edge.Click += delegate {
            if (!Allow("允许打开 Edge 扩展管理页吗？用途：由你手动开启开发人员模式并加载插件。不会关闭现有网页。")) return;
            string executable = new[] { Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData) }
                .Where(p => !String.IsNullOrEmpty(p)).Select(p => Path.Combine(p, "Microsoft", "Edge", "Application", "msedge.exe")).FirstOrDefault(File.Exists);
            if (executable == null) { status.Text = "未找到 Edge。请自行打开 Edge，在地址栏输入 edge://extensions。"; return; }
            try { Process.Start(new ProcessStartInfo(executable, "edge://extensions/") { UseShellExecute = true }); }
            catch (Exception) { status.Text = "未能打开 Edge，请自行在 Edge 地址栏输入 edge://extensions。"; }
        };
        folder.Click += delegate {
            if (!Allow("允许打开插件文件夹吗？用途：查看已保存的文件并找到 Edge 要加载的目录。")) return;
            try { Process.Start(new ProcessStartInfo("explorer.exe", "\"" + target + "\"") { UseShellExecute = true }); }
            catch (Exception) { status.Text = "未能打开文件夹，请复制上方路径到资源管理器。"; }
        };
        copy.Click += delegate {
            try { Clipboard.SetText(target); status.Text = "路径已复制。Edge → 加载解压缩的扩展 → 将路径粘贴到目录选择框并确认。"; }
            catch (Exception) { status.Text = "无法复制，请在上方文本框选中路径并手动复制。"; }
        };
        Controls.Add(instructions); Controls.Add(path); Controls.Add(status);
    }
    bool Allow(string purpose) { return MessageBox.Show(this, purpose, "操作权限确认", MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) == DialogResult.Yes; }
    [STAThread]
    public static void Main() { Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new CollectorSetup()); }
}
