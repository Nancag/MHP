using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

[assembly: AssemblyTitle("MHP Windows Client")]
[assembly: AssemblyProduct("MHP")]
[assembly: AssemblyCompany("MHP")]
[assembly: AssemblyVersion(MhpClient.ClientVersion.Assembly)]
[assembly: AssemblyFileVersion(MhpClient.ClientVersion.Assembly)]

namespace MhpClient
{
    internal static class Program
    {
        internal const string Server = "https://118.178.92.58/";
        internal static string Home = Server;
        internal static string Profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MHP", "WebView2");
#if QA
        internal static string QaFolder;
        internal static bool CloudOnly;
        internal static bool UseBundle;
#endif
        [DllImport("user32.dll")] private static extern bool SetProcessDPIAware();

        [STAThread]
        private static int Main(string[] args)
        {
            if(args.Length==2&&args[0]=="--verify-update") {try{UpdateClient.Verify(File.ReadAllBytes(args[1]));return 0;}catch{return 4;}}
            if(args.Length==1&&args[0]=="--verify-bundle") {try{using(var bundle=new BundledFrontend()){string mime;return bundle.Read(new Uri(Server),"GET",out mime)==null?5:0;}}catch{return 5;}}
            if (args.Contains("--check-runtime"))
            {
                try { CoreWebView2Environment.GetAvailableBrowserVersionString(); return 0; }
                catch { return 2; }
            }
#if QA
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--qa-folder" && i + 1 < args.Length) QaFolder = Path.GetFullPath(args[++i]);
                if (args[i] == "--qa-url" && i + 1 < args.Length)
                {
                    Uri url = new Uri(args[++i]);
                    if ((url.Scheme != "http" && url.Scheme != "https") || url.Host != "127.0.0.1") return 3;
                    Home = url.AbsoluteUri;
                }
                if (args[i] == "--qa-cloud") CloudOnly = true;
                if (args[i] == "--qa-bundled") UseBundle = true;
            }
            if (String.IsNullOrEmpty(QaFolder)) return 3;
            Directory.CreateDirectory(QaFolder);
            Profile = Path.Combine(QaFolder, "profile");
#else
            // Release builds never accept a remote-debugging flag or another server.
            if (args.Length != 0) return 3;
#endif
            SetProcessDPIAware();
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
            Application.ThreadException += delegate { MessageBox.Show("MHP 操作未完成，请重试或重新打开客户端。", "MHP", MessageBoxButtons.OK, MessageBoxIcon.Error); };
            try
            {
#if QA
                Application.Run(new MainWindow());
#else
                bool first;
                using (var instance = new System.Threading.Mutex(true, "Local\\MHPBetaClient", out first))
                {
                    if (!first) { MessageBox.Show("MHP 已经打开，请从任务栏进入。", "MHP"); return 0; }
                    Application.Run(new MainWindow());
                }
#endif
                return 0;
            }
            catch { MessageBox.Show("MHP 启动失败，请重新安装客户端或联系维护人员。", "MHP", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1; }
        }
    }

    internal sealed class MainWindow : Form
    {
        private readonly WebView2 web = new WebView2();
        private readonly ToolStripStatusLabel status = new ToolStripStatusLabel("正在连接 MHP…");
        private readonly Panel fallback = new Panel { Dock = DockStyle.Fill, Visible = false, BackColor = Color.FromArgb(246, 249, 253) };
        private readonly Label message = new Label { AutoSize = false, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter };
        private bool closing;
        private readonly Timer updateTimer=new Timer {Interval=15*60*1000};
        private bool checkingUpdate;
        private string offeredVersion;
        private BundledFrontend frontend;
#if QA
        private readonly Timer qaTimer = new Timer { Interval = 250 };
#endif

        internal MainWindow()
        {
            Text = "MHP " + ClientVersion.Current + " · Windows · 本机界面";
            ClientSize = new Size(1360, 900);
            MinimumSize = new Size(1000, 720);
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Microsoft YaHei UI", 9F);
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            var toolbar = new ToolStrip { GripStyle = ToolStripGripStyle.Hidden, Padding = new Padding(8, 4, 8, 4) };
            var home = new ToolStripButton("回到首页");
            home.Click += delegate { if (web.CoreWebView2 != null) web.CoreWebView2.Navigate(Program.Home); };
            var reload = new ToolStripButton("刷新 / 重试");
            reload.Click += delegate { if (web.CoreWebView2 != null) web.Reload(); };
            var about = new ToolStripButton("关于") { Alignment = ToolStripItemAlignment.Right };
            about.Click += delegate { MessageBox.Show("MHP " + ClientVersion.Current + "（未签名）\n\n前端界面已打包在客户端中，从本机加载。\n登录、历史及 AI 生成连接云端服务。\n启动时及每15分钟检查更新，安装前由你确认。\n账号资料与用户图片保留。\n\n服务地址：" + Program.Server, "关于 MHP"); };
            var update=new ToolStripButton("检查更新 · " + ClientVersion.Current);update.Click+=async delegate{await CheckUpdate(true);};toolbar.Items.Add(update);
            toolbar.Items.Add(home); toolbar.Items.Add(reload); toolbar.Items.Add(about);
            var bar = new StatusStrip(); bar.Items.Add(status);
            web.Dock = DockStyle.Fill;
            Controls.Add(web); Controls.Add(fallback); Controls.Add(toolbar); Controls.Add(bar);
            fallback.Controls.Add(message);
            Shown += async delegate { await Initialize();
#if !QA
                try{UpdateClient.CleanupOldVersions();}catch{}await CheckUpdate(false);updateTimer.Start();
#endif
            };
            updateTimer.Tick+=async delegate{await CheckUpdate(false);};
            FormClosing += OnClosing;
#if QA
            ShowInTaskbar = false;
            Opacity = .01;
            qaTimer.Tick += delegate
            {
                File.WriteAllText(Path.Combine(Program.QaFolder, "native-state.txt"), status.Text + "\nerror_visible=" + fallback.Visible);
                string command = Path.Combine(Program.QaFolder, "native-command.txt");
                if (!File.Exists(command)) return;
                string action = File.ReadAllText(command).Trim();
                File.Delete(command);
                if (action == "home") home.PerformClick();
                if (action == "reload") reload.PerformClick();
                if (action == "close") { qaTimer.Stop(); Close(); }
            };
            qaTimer.Start();
#endif
        }

        private async Task CheckUpdate(bool manual)
        {
            if(checkingUpdate||closing)return;checkingUpdate=true;
            try {
                var release=await UpdateClient.Check();
                if(release.Version<=new Version(UpdateClient.Current)){status.Text="MHP " + ClientVersion.Current + " · 已是最新版本";if(manual)MessageBox.Show(this,"当前版本 " + ClientVersion.Current + "，已是最新版本。","MHP 更新");return;}
                status.Text="发现新版本 "+release.Version.ToString(3)+" · 当前 " + ClientVersion.Current;
                if(!manual&&offeredVersion==release.Version.ToString(3))return;offeredVersion=release.Version.ToString(3);
                if(MessageBox.Show(this,"当前版本：" + ClientVersion.Current + "\n新版本："+release.Version.ToString(3)+"\n\n"+release.Notes+"\n\n是否下载更新？选择否可继续使用当前版本。","MHP 更新",MessageBoxButtons.YesNo,MessageBoxIcon.Information)!=DialogResult.Yes)return;
                status.Text="正在下载并校验更新…";string file=await UpdateClient.Download(release);
                if(MessageBox.Show(this,"更新包已校验。现在关闭 MHP 并启动安装程序？","安装更新",MessageBoxButtons.YesNo)!=DialogResult.Yes){status.Text="更新已下载，可稍后安装";return;}
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(file){UseShellExecute=true});Close();
            }catch{status.Text="MHP " + ClientVersion.Current + " · 更新检查未完成，可稍后重试";if(manual)MessageBox.Show(this,"更新检查或校验未完成。当前版本可继续使用，请稍后重试。","MHP 更新");}
            finally{checkingUpdate=false;}
        }

        private bool Allowed(string address)
        {
            Uri target;
            if (!Uri.TryCreate(address, UriKind.Absolute, out target)) return false;
            Uri home = new Uri(Program.Home);
            return target.Scheme == home.Scheme && target.Host == home.Host && target.Port == home.Port;
        }

        private void Failed(string text)
        {
            status.Text = "连接未完成，可点击刷新重试";
            message.Text = text;
            fallback.Visible = true;
            fallback.BringToFront();
        }

        private async Task Initialize()
        {
            try
            {
                Directory.CreateDirectory(Program.Profile);
                var options = new CoreWebView2EnvironmentOptions();
#if QA
                options.AdditionalBrowserArguments = "--remote-debugging-port=9226";
#endif
                var environment = await CoreWebView2Environment.CreateAsync(null, Program.Profile, options);
                await web.EnsureCoreWebView2Async(environment);
                var core = web.CoreWebView2;
                core.Settings.AreDevToolsEnabled = false;
                core.Settings.IsStatusBarEnabled = false;
                core.Settings.AreHostObjectsAllowed = false;
                core.Settings.IsWebMessageEnabled = false;
                core.Settings.AreDefaultContextMenusEnabled = false;
                core.Settings.IsGeneralAutofillEnabled = false;
                core.Settings.IsPasswordAutosaveEnabled = false;
                await core.AddScriptToExecuteOnDocumentCreatedAsync("Object.defineProperty(window,'__MHP_NATIVE__',{value:true});Object.defineProperty(window,'__MHP_CLIENT_VERSION__',{value:'" + ClientVersion.Current + "'});Object.defineProperty(window,'__MHP_BUNDLED_FRONTEND__',{value:true});");
#if QA
                if (Program.UseBundle)
#endif
                {
                    frontend = new BundledFrontend();
                    core.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
                    core.WebResourceRequested += delegate(object sender, CoreWebView2WebResourceRequestedEventArgs e) {
                        Uri uri;
                        if (!Uri.TryCreate(e.Request.Uri, UriKind.Absolute, out uri) || !Allowed(e.Request.Uri) || BundledFrontend.IsApi(uri)) return;
                        string mime;
                        byte[] data = frontend.Read(uri, e.Request.Method, out mime);
                        e.Response = environment.CreateWebResourceResponse(new MemoryStream(data ?? new byte[0]), data == null ? 404 : 200,
                            data == null ? "Not Found" : "OK", "Content-Type: " + mime + "\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-MHP-Frontend: bundled\r\n");
                    };
                }
                await core.Profile.SetPermissionStateAsync(CoreWebView2PermissionKind.MultipleAutomaticDownloads,
                    new Uri(Program.Home).GetLeftPart(UriPartial.Authority), CoreWebView2PermissionState.Allow);
                core.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e)
                {
                    if (!Allowed(e.Uri)) { e.Cancel = true; status.Text = "客户端仅打开 MHP 服务内的页面。"; return; }
                    fallback.Visible = false;
                    status.Text = "正在加载 MHP…";
                };
                core.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e)
                {
                    if (e.IsSuccess) status.Text = "MHP 本机界面 · " + ClientVersion.Current + " · 云端 " + new Uri(Program.Home).Host;
                    else Failed("暂时无法打开 MHP。\n\n请检查网络、服务器及 HTTPS 证书，然后点击“刷新 / 重试”。\n错误类型：" + e.WebErrorStatus);
                };
                core.ServerCertificateErrorDetected += delegate(object sender, CoreWebView2ServerCertificateErrorDetectedEventArgs e)
                {
                    e.Action = CoreWebView2ServerCertificateErrorAction.Cancel;
#if QA
                    File.WriteAllText(Path.Combine(Program.QaFolder, "certificate-blocked.json"), "{\"invalid_certificate_blocked\":true}");
#endif
                    Failed("MHP 的 HTTPS 证书未通过验证。\n请联系维护人员修复服务器证书后重试。");
                };
                core.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e)
                {
                    e.Handled = true;
                    if (Allowed(e.Uri)) core.Navigate(e.Uri);
                    else status.Text = "外部链接请在浏览器中打开。";
                };
                core.PermissionRequested += delegate(object sender, CoreWebView2PermissionRequestedEventArgs e)
                {
#if QA
                    File.AppendAllText(Path.Combine(Program.QaFolder, "permissions.txt"), e.PermissionKind + " allowed_origin=" + Allowed(e.Uri) + "\n");
#endif
                    // Every release download still requires its own Windows save dialog.
                    e.State = e.PermissionKind == CoreWebView2PermissionKind.MultipleAutomaticDownloads && Allowed(e.Uri)
                        ? CoreWebView2PermissionState.Allow : CoreWebView2PermissionState.Deny;
                };
                core.DownloadStarting += DownloadStarting;
                core.ProcessFailed += delegate { Failed("图片窗口暂时停止响应，请关闭客户端后重新打开。"); };
                await ClearSessionCookies();
#if QA
                core.DownloadStarting += delegate { };
                await core.CallDevToolsProtocolMethodAsync("Network.enable", "{}");
                File.WriteAllText(Path.Combine(Program.QaFolder, "ready.json"), "{\"ready\":true,\"native_webview\":true}");
                core.NavigationCompleted += async delegate(object sender, CoreWebView2NavigationCompletedEventArgs e)
                {
                    if (Program.CloudOnly)
                    {
                        File.WriteAllText(Path.Combine(Program.QaFolder, "cloud.json"), "{\"navigation_success\":" + e.IsSuccess.ToString().ToLowerInvariant() + ",\"error\":\"" + e.WebErrorStatus + "\"}");
                        if (e.IsSuccess)
                        {
                            string title = await core.ExecuteScriptAsync("document.title");
                            File.WriteAllText(Path.Combine(Program.QaFolder, "cloud-title.json"), title);
                        }
                    }
                };
#endif
                core.Navigate(Program.Home);
            }
            catch (WebView2RuntimeNotFoundException)
            {
                Failed("缺少 Microsoft Edge WebView2 运行时。\n请重新运行 MHP 安装包，或安装微软官方 WebView2 运行时。");
            }
            catch
            {
                Failed("MHP 初始化失败。\n请检查 WebView2 运行时及本机用户目录是否可写，然后重新打开客户端。");
            }
        }

        private void DownloadStarting(object sender, CoreWebView2DownloadStartingEventArgs e)
        {
#if QA
            File.AppendAllText(Path.Combine(Program.QaFolder, "downloads.txt"), Path.GetFileName(e.ResultFilePath) + "\n");
#endif
            string filename = Path.GetFileName(e.ResultFilePath);
            string extension = Path.GetExtension(filename).ToLowerInvariant();
            if (!new[] { ".png", ".jpg", ".jpeg", ".webp", ".zip" }.Contains(extension))
            {
                e.Cancel = true;
                status.Text = "客户端支持保存 PNG、JPG、WEBP 图片和 ZIP 套图。";
                return;
            }
            e.Handled = true;
#if QA
            e.ResultFilePath = Path.Combine(Program.QaFolder, filename);
#else
            using (var dialog = new SaveFileDialog())
            {
                dialog.Title = "保存 MHP 成品";
                dialog.FileName = filename;
                dialog.DefaultExt = extension.TrimStart('.');
                dialog.Filter = "成品文件 (*" + extension + ")|*" + extension;
                dialog.AddExtension = true;
                dialog.OverwritePrompt = true;
                if (dialog.ShowDialog(this) != DialogResult.OK) { e.Cancel = true; return; }
                e.ResultFilePath = dialog.FileName;
            }
#endif
            var download = e.DownloadOperation;
            status.Text = "正在保存 " + filename;
            download.StateChanged += delegate
            {
                if (download.State == CoreWebView2DownloadState.Completed) status.Text = "已保存 " + filename;
                else if (download.State == CoreWebView2DownloadState.Interrupted) status.Text = "保存中断，请重试。";
            };
        }

        private async void OnClosing(object sender, FormClosingEventArgs e)
        {
            if (closing || web.CoreWebView2 == null) return;
            e.Cancel = true;
            closing = true;
            await ClearSessionCookies();
            Close();
        }

        private async Task ClearSessionCookies()
        {
            try
            {
                // Keep persistent "remember me" cookies; session-only logins expire on exit.
                var pending = web.CoreWebView2.CookieManager.GetCookiesAsync(Program.Home);
                if (await Task.WhenAny(pending, Task.Delay(2000)) != pending) return;
                foreach (var cookie in (await pending).Where(cookie => cookie.IsSession)) web.CoreWebView2.CookieManager.DeleteCookie(cookie);
            }
            catch { }
        }
    }
}
