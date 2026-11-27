; Instalador Windows do Extrator CNPq Lattes (Inno Setup 6), feito a partir da pasta onedir do
; PyInstaller. Chamado pelo ci/build_windows.sh:
;   iscc -DVersao=2.1.0 -DVersaoNum=2.1.0.0 -DOrigem=<pasta ExtratorLattes> -O<saída> ci/ExtratorLattes.iss
; Instala por usuário em %LOCALAPPDATA%\Programs\ExtratorLattes, sem pedir administrador.
; Caminhos relativos partem da pasta deste script (ci/).

#ifndef Versao
  #define Versao "0.0.0"
#endif
#ifndef VersaoNum
  #define VersaoNum "0.0.0.0"
#endif
#ifndef Origem
  #define Origem "..\build-ci\windows\dist\ExtratorLattes"
#endif

#define Nome "Extrator CNPq Lattes"
#define Exe "ExtratorLattes.exe"

[Setup]
; AppId fixo: identifica o programa nas atualizações e no desinstalador. Não mudar.
AppId={{262A4898-267A-4756-8659-01C061773C43}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher=Extrator CNPq Lattes
AppPublisherURL=https://github.com/o-accioly/extrator-cnpq-lattes
AppSupportURL=https://github.com/o-accioly/extrator-cnpq-lattes/issues
AppUpdatesURL=https://github.com/o-accioly/extrator-cnpq-lattes/releases/latest
DefaultDirName={localappdata}\Programs\ExtratorLattes
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=ExtratorLattes-{#Versao}-setup
SetupIconFile=..\lattes_extrator\data\icone.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nome}
VersionInfoVersion={#VersaoNum}
VersionInfoProductVersion={#VersaoNum}
VersionInfoTextVersion={#Versao}
VersionInfoProductTextVersion={#Versao}
VersionInfoProductName={#Nome}
VersionInfoDescription=Instalador do {#Nome}
VersionInfoCompany=Extrator CNPq Lattes
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Atualização: tira os arquivos da versão anterior para não misturar bibliotecas.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Origem}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Exe}"
Name: "{group}\{cm:UninstallProgram,{#Nome}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#Nome}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Exe}"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent
