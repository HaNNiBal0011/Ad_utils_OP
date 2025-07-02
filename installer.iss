
[Setup]
AppName=RDP Manager
AppVersion=1.0.0
AppPublisher=IT Department
AppPublisherURL=http://internal.company.com
DefaultDirName={autopf}\RDPManager
DefaultGroupName=RDP Manager
UninstallDisplayIcon={app}\RDPManager.exe
Compression=lzma2
SolidCompression=yes
OutputDir=installer
OutputBaseFilename=RDPManager_Setup

[Files]
Source: "dist\RDPManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\RDP Manager"; Filename: "{app}\RDPManager.exe"
Name: "{group}\Удалить RDP Manager"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RDP Manager"; Filename: "{app}\RDPManager.exe"

[Run]
Filename: "{app}\RDPManager.exe"; Description: "Запустить RDP Manager"; Flags: nowait postinstall skipifsilent
