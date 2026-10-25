using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace MhpClient {
 internal sealed class ReleaseInfo { internal Version Version; internal string Url, Hash, Notes; internal long Bytes; }
 internal static class UpdateClient {
  internal const string Current=ClientVersion.Current;
#if QA
  internal static Func<HttpClient> ClientFactory=()=>new HttpClient();
#else
  private static HttpClient ClientFactory(){return new HttpClient();}
#endif
  internal static readonly string Cache=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MHP","updates");
  internal static ReleaseInfo Verify(byte[] envelope) {
   if(envelope.Length>65536)throw new InvalidDataException("更新信息过大");
   var json=new JavaScriptSerializer();var outer=json.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(envelope));
   byte[] payload=Convert.FromBase64String((string)outer["payload"]),signature=Convert.FromBase64String((string)outer["signature"]);
   using(var rsa=new RSACryptoServiceProvider()) {rsa.PersistKeyInCsp=false;rsa.FromXmlString(UpdateKey.PublicXml);if(!rsa.VerifyData(payload,CryptoConfig.MapNameToOID("SHA256"),signature))throw new CryptographicException("发布签名无效");}
   var value=json.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(payload));
   var result=new ReleaseInfo {Version=new Version((string)value["version"]),Url=(string)value["url"],Hash=(string)value["sha256"],Bytes=Convert.ToInt64(value["size_bytes"]),Notes=(string)value["notes"]};
   if(result.Version.Build<0||result.Version.Revision>0)throw new InvalidDataException("版本号无效");
   Uri uri=new Uri(new Uri(Program.Server),result.Url),home=new Uri(Program.Server);
   string expected="/downloads/windows/MHP-Setup-"+result.Version.ToString(3)+"-x64.exe";
   if(uri.Scheme!="https"||uri.Host!=home.Host||uri.Port!=home.Port||uri.AbsolutePath!=expected||uri.Query!=""||uri.Fragment!=""||uri.UserInfo!="")throw new InvalidDataException("更新地址无效");
   if(result.Hash.Length!=64||result.Hash.Any(c=>!Uri.IsHexDigit(c))||result.Bytes<1000||result.Bytes>100*1024*1024)throw new InvalidDataException("更新校验信息无效");
   result.Url=uri.AbsoluteUri;return result;
  }
  internal static async Task<ReleaseInfo> Check() {using(var client=ClientFactory()) {client.Timeout=TimeSpan.FromSeconds(20);client.MaxResponseContentBufferSize=65536;return Verify(await client.GetByteArrayAsync(new Uri(new Uri(Program.Server),"client-release.json")));}}
  internal static async Task<string> Download(ReleaseInfo release) {
   if(release.Version<=new Version(Current))throw new InvalidOperationException("不允许降级");
   Directory.CreateDirectory(Cache);if((new DirectoryInfo(Cache).Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException("更新目录不可用");string folder=Path.Combine(Cache,release.Version.ToString(3));Directory.CreateDirectory(folder);
   if((new DirectoryInfo(folder).Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException("更新目录不可用");
   File.WriteAllText(Path.Combine(folder,".mhp-update-cache"),release.Version.ToString(3));
   string target=Path.Combine(folder,"MHP-Setup-"+release.Version.ToString(3)+"-x64.exe"),partial=target+".partial";
   try {
    using(var client=ClientFactory()) {client.Timeout=TimeSpan.FromMinutes(5);using(var response=await client.GetAsync(release.Url,HttpCompletionOption.ResponseHeadersRead)) {
     response.EnsureSuccessStatusCode();long received=0;
     using(var input=await response.Content.ReadAsStreamAsync())using(var output=new FileStream(partial,FileMode.Create,FileAccess.Write,FileShare.None)) {
      byte[] buffer=new byte[65536];int count;while((count=await input.ReadAsync(buffer,0,buffer.Length))>0){received+=count;if(received>release.Bytes)throw new InvalidDataException("文件大小不符");await output.WriteAsync(buffer,0,count);}}
     if(received!=release.Bytes)throw new InvalidDataException("下载不完整");}}
    using(var sha=SHA256.Create())using(var input=File.OpenRead(partial)){string actual=BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant();if(!String.Equals(actual,release.Hash,StringComparison.OrdinalIgnoreCase))throw new CryptographicException("更新包校验失败");}
    if(File.Exists(target))File.Delete(target);File.Move(partial,target);return target;
   }catch{if(File.Exists(partial))File.Delete(partial);throw;}
  }
  internal static int CleanupOldVersions() {
   if(!Directory.Exists(Cache))return 0;string root=Path.GetFullPath(Cache).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
   if((new DirectoryInfo(Cache).Attributes&FileAttributes.ReparsePoint)!=0)return 0;int count=0;
   foreach(string folder in Directory.GetDirectories(Cache)){Version version;if(!Version.TryParse(Path.GetFileName(folder),out version)||version>=new Version(Current))continue;
    string resolved=Path.GetFullPath(folder);if(!resolved.StartsWith(root,StringComparison.OrdinalIgnoreCase)||!File.Exists(Path.Combine(folder,".mhp-update-cache")))continue;
    try{if(File.ReadAllText(Path.Combine(folder,".mhp-update-cache")).Trim()!=version.ToString(3)||!SafeTree(new DirectoryInfo(folder)))continue;Directory.Delete(resolved,true);count++;}catch(IOException){}catch(UnauthorizedAccessException){}
   }return count;
  }
  private static bool SafeTree(DirectoryInfo directory){if((directory.Attributes&FileAttributes.ReparsePoint)!=0)return false;foreach(var entry in directory.GetFileSystemInfos()){if((entry.Attributes&FileAttributes.ReparsePoint)!=0)return false;var child=entry as DirectoryInfo;if(child!=null&&!SafeTree(child))return false;}return true;}
 }
}
