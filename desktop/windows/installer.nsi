Unicode true
!ifndef VERSION
 !error "Build must provide VERSION and VERSIONQUAD"
!endif
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "MHP 内测版"
OutFile "${OUTPUT}\MHP-Setup-${VERSION}-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\MHP Beta"
!ifdef QA
 !define UNINSTALL_KEY "Software\MHP\IsolatedBundleQA"
 !define CLIENT_MUTEX "Local\MHPIsolatedBundleQA"
!else
 !define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\MHPBeta"
 !define CLIENT_MUTEX "Local\MHPBetaClient"
!endif
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${VERSIONQUAD}"
VIAddVersionKey /LANG=2052 "ProductName" "MHP 内测版"
VIAddVersionKey /LANG=2052 "CompanyName" "MHP"
VIAddVersionKey /LANG=2052 "FileDescription" "MHP Windows x64 内测安装包（未签名）"
VIAddVersionKey /LANG=2052 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=2052 "LegalCopyright" "MHP"
!define MUI_ICON "${SOURCE}\mhp.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "安装 MHP Windows 内测版"
!define MUI_WELCOMEPAGE_TEXT "本版本未签名，供内测使用。需要联网，连接 https://118.178.92.58。$\r$\n$\r$\n账户、额度和历史记录与网页共用。Windows 10/11 x64，需要 .NET Framework 4.8 和微软 WebView2。缺少 WebView2 时会安装微软官方运行时。$\r$\n$\r$\n程序安装在当前用户目录。"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\MHP.exe"
!define MUI_FINISHPAGE_RUN_TEXT "启动 MHP"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
 SetShellVarContext current
 StrCpy $2 0
 check_running:
 System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "${CLIENT_MUTEX}") p.r0'
 ${If} $0 != 0
  System::Call 'kernel32::CloseHandle(p r0)'
  IntOp $2 $2 + 1
  ${If} $2 < 40
   Sleep 250
   Goto check_running
  ${EndIf}
  MessageBox MB_OK|MB_ICONSTOP "请先关闭正在运行的 MHP，再运行安装包。账号资料将保留。"
  Abort
 ${EndIf}
 ${IfNot} ${RunningX64}
  MessageBox MB_OK|MB_ICONSTOP "此安装包需要 64 位 Windows。"
  Abort
 ${EndIf}
 ${IfNot} ${AtLeastWin10}
  MessageBox MB_OK|MB_ICONSTOP "此内测版支持 Windows 10/11。"
  Abort
 ${EndIf}
 SetRegView 64
 ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full" "Release"
 ${If} $0 < 528040
  MessageBox MB_OK|MB_ICONSTOP "请先安装微软 .NET Framework 4.8，再运行安装包。"
  Abort
 ${EndIf}
FunctionEnd

Section "MHP"
 SetOutPath "$INSTDIR"
 File "${SOURCE}\MHP.exe"
 File "${SOURCE}\MHP.exe.config"
 File "${SOURCE}\Microsoft.Web.WebView2.Core.dll"
 File "${SOURCE}\Microsoft.Web.WebView2.WinForms.dll"
 File "${SOURCE}\WebView2Loader.dll"
 File "${SOURCE}\mhp.ico"
 File "${SOURCE}\README.txt"
 File "${SOURCE}\WebView2-LICENSE.txt"
 File "${SOURCE}\MicrosoftEdgeWebview2Setup.exe"
 ExecWait '"$INSTDIR\MHP.exe" --check-runtime' $0
 ${If} $0 != 0
  DetailPrint "安装微软 WebView2 运行时…"
  ExecWait '"$INSTDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install' $1
  ExecWait '"$INSTDIR\MHP.exe" --check-runtime' $0
  ${If} $0 != 0
   IfSilent +2
   MessageBox MB_OK|MB_ICONSTOP "WebView2 安装未完成。请从微软官方网站安装运行时后重试。"
   SetErrorLevel 2
   Abort
  ${EndIf}
 ${EndIf}
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "MHP 内测版"
 WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
 WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "MHP"
 WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
 WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\MHP.exe"
 WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
 WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
!ifndef QA
 CreateDirectory "$SMPROGRAMS\MHP 内测版"
 CreateShortcut "$SMPROGRAMS\MHP 内测版\MHP.lnk" "$INSTDIR\MHP.exe"
 CreateShortcut "$SMPROGRAMS\MHP 内测版\卸载 MHP.lnk" "$INSTDIR\Uninstall.exe"
 CreateShortcut "$DESKTOP\MHP 内测版.lnk" "$INSTDIR\MHP.exe"
!endif
SectionEnd

Section "Uninstall"
 SetShellVarContext current
 SetRegView 64
 Delete "$INSTDIR\MHP.exe"
 Delete "$INSTDIR\MHP.exe.config"
 Delete "$INSTDIR\Microsoft.Web.WebView2.Core.dll"
 Delete "$INSTDIR\Microsoft.Web.WebView2.WinForms.dll"
 Delete "$INSTDIR\WebView2Loader.dll"
 Delete "$INSTDIR\mhp.ico"
 Delete "$INSTDIR\README.txt"
 Delete "$INSTDIR\WebView2-LICENSE.txt"
 Delete "$INSTDIR\MicrosoftEdgeWebview2Setup.exe"
 Delete "$INSTDIR\Uninstall.exe"
!ifndef QA
 Delete "$DESKTOP\MHP 内测版.lnk"
 Delete "$SMPROGRAMS\MHP 内测版\MHP.lnk"
 Delete "$SMPROGRAMS\MHP 内测版\卸载 MHP.lnk"
 RMDir "$SMPROGRAMS\MHP 内测版"
!endif
 RMDir "$INSTDIR"
 DeleteRegKey HKCU "${UNINSTALL_KEY}"
 ; Preserve the WebView2 profile, persistent login, and all server-side user data.
SectionEnd
