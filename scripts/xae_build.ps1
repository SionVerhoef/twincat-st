<#
Build a TwinCAT solution in a hidden XAE and print the compiler output. It never activates and
changes no controller. It starts its own XAE process. An XAE with a DIFFERENT solution open is
left alone. One with the SAME solution open keeps running, but within a second of the build it
asks "<PLC>.xti was modified outside of TwinCAT XAE. Do you want to reload it?" - answer Yes;
No keeps the old .xti in memory and writes it back on the next save. The hidden XAE also
rewrites the shared .vs\<sln>\v15\.suo when it quits. Ask the user to close the solution first,
or to expect that prompt. When the solution's lock file names a live XAE, the script says so.
Exit code: 0 = every project built, 1 = a project failed (SolutionBuild.LastBuildInfo) or the
script could not run.

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_build.ps1 -Solution <x.sln>
      [-TreePath 'TIPC^PLC1^PLC1 Project^POUs^FB_X']   list that tree item and its children (methods, properties)
      [-SaveAll]                                       Save All after the build, to see what XAE rewrites
      [-Rebuild]                                       Clean first. This lays out PLC memory anew, so the
                                                       .tmc/.xti differ from an incremental build in XAE
      [-ProgId 'TcXaeShell.DTE.15.0']                  XAE integrated in Visual Studio: 'VisualStudio.DTE.<ver>'
      [-PublicAssemblies '<IDE>\PublicAssemblies']     where envdte.dll lives for that XAE

It builds the files on disk; unsaved edits in an open XAE are not included. Like a build in XAE, it
writes the PLC's .tmc, the .xti (TmcHash) and _CompileInfo, and rewrites a Measurement project's .vsm.
Needs Windows PowerShell 5.1 (powershell.exe); PowerShell 7 lacks the COM/Add-Type support used here.
See references/twincat/xae-automation.md.
#>
param(
    [Parameter(Mandatory)] [string] $Solution,
    [string] $TreePath = '',
    [switch] $SaveAll,
    [switch] $Rebuild,
    [string] $ProgId = 'TcXaeShell.DTE.15.0',
    [string] $PublicAssemblies = 'C:\Program Files (x86)\Beckhoff\TcXaeShell\Common7\IDE\PublicAssemblies'
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path "$PublicAssemblies\envdte.dll")) {
    # Not Write-Error: under $ErrorActionPreference = 'Stop' it throws, prints a full error
    # record with the script position, and never reaches the exit below.
    [Console]::Error.WriteLine("envdte.dll not found in '$PublicAssemblies'. Pass -PublicAssemblies for this XAE install.")
    exit 1
}

# While a solution is open, XAE keeps <project>.project.~u beside it: three lines - user,
# machine, PID - rewritten about every 35 s. A live PID there is an XAE that will ask to
# reload the .xti once this build rewrites it.
$slnPath = (Resolve-Path $Solution).Path
foreach ($lock in Get-ChildItem -Path (Split-Path $slnPath) -Filter '*.project.~u' -File -Recurse -Depth 2 -ErrorAction SilentlyContinue) {
    $lines = @(Get-Content $lock.FullName -ErrorAction SilentlyContinue)
    $lockPid = 0
    if ($lines.Count -ge 3 -and [int]::TryParse($lines[2].Trim(), [ref]$lockPid) -and (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)) {
        "WARNING: the solution is open in XAE (PID $lockPid): it will ask to reload the .xti; answer Yes"
    }
}

# XAE rejects COM calls while it is busy (RPC_E_CALL_REJECTED); this filter retries them.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("00000016-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IOleMessageFilter {
    [PreserveSig] int HandleInComingCall(int t, IntPtr h, int ti, IntPtr i);
    [PreserveSig] int RetryRejectedCall(IntPtr h, int ti, int r);
    [PreserveSig] int MessagePending(IntPtr h, int ti, int p);
}
public class MessageFilter : IOleMessageFilter {
    [DllImport("Ole32.dll")] static extern int CoRegisterMessageFilter(IOleMessageFilter n, out IOleMessageFilter o);
    public static void Register()   { IOleMessageFilter o; CoRegisterMessageFilter(new MessageFilter(), out o); }
    public static void Revoke()     { IOleMessageFilter o; CoRegisterMessageFilter(null, out o); }
    int IOleMessageFilter.HandleInComingCall(int t, IntPtr h, int ti, IntPtr i) { return 0; }
    int IOleMessageFilter.RetryRejectedCall(IntPtr h, int ti, int r) { return r == 2 ? 99 : -1; }
    int IOleMessageFilter.MessagePending(IntPtr h, int ti, int p) { return 2; }
}
"@

# From PowerShell, late-bound DTE returns the Error List and Output panes empty; early-bound
# EnvDTE from XAE's own PublicAssemblies reads them.
[void][Reflection.Assembly]::LoadFrom("$PublicAssemblies\envdte.dll")
[void][Reflection.Assembly]::LoadFrom("$PublicAssemblies\envdte80.dll")
Add-Type -ReferencedAssemblies "$PublicAssemblies\envdte.dll","$PublicAssemblies\envdte80.dll" -TypeDefinition @"
using System; using System.Text;
public static class XaeDump {
    // compilerOnly: skip entries without a project or file, i.e. the target's logger lines.
    public static string Errors(object o, bool compilerOnly) {
        var dte = (EnvDTE80.DTE2)o; var sb = new StringBuilder();
        var items = dte.ToolWindows.ErrorList.ErrorItems;
        for (int i = 1; i <= items.Count; i++) {
            var e = items.Item(i);
            if (compilerOnly && string.IsNullOrEmpty(e.Project) && string.IsNullOrEmpty(e.FileName)) continue;
            string lvl = e.ErrorLevel == EnvDTE80.vsBuildErrorLevel.vsBuildErrorLevelHigh ? "Error"
                       : e.ErrorLevel == EnvDTE80.vsBuildErrorLevel.vsBuildErrorLevelMedium ? "Warning" : "Message";
            sb.AppendLine(lvl + ": " + e.Description + (string.IsNullOrEmpty(e.FileName) ? "" : " | " + e.FileName + ":" + e.Line));
        }
        return sb.ToString();
    }
    public static string Pane(object o, string name) {
        var dte = (EnvDTE80.DTE2)o;
        foreach (EnvDTE.OutputWindowPane pane in dte.ToolWindows.OutputWindow.OutputWindowPanes) {
            if (pane.Name != name) continue;
            var doc = pane.TextDocument;
            return doc.StartPoint.CreateEditPoint().GetText(doc.EndPoint);
        }
        return "(no '" + name + "' pane)";
    }
}
"@

function Show-Tree($item, $indent) {
    "$indent$($item.Name)"
    for ($i = 1; $i -le $item.ChildCount; $i++) { Show-Tree $item.Child($i) ($indent + '  ') }
}

$dte = $null
$failed = 1
try {
    [MessageFilter]::Register()
    $dte = New-Object -ComObject $ProgId
    $dte.SuppressUI = $true
    $dte.MainWindow.Visible = $false
    $dte.Solution.Open($slnPath)
    $dte.ExecuteCommand('View.Output')
    $dte.ExecuteCommand('View.ErrorList')

    $sysMan = $dte.Solution.Projects.Item(1).Object
    if ($TreePath) { "=== Tree under $TreePath ==="; Show-Tree ($sysMan.LookupTreeItem($TreePath)) '' }

    $sb = $dte.Solution.SolutionBuild
    if ($Rebuild) { $sb.Clean($true) }
    $sb.Build($true)
    Start-Sleep -Seconds 2    # let the Error List catch up

    "=== Build pane ==="
    [XaeDump]::Pane($dte, 'Build')
    "=== Error List (compiler) ==="
    [XaeDump]::Errors($dte, $true)
    $failed = $sb.LastBuildInfo
    "=== Projects failed: $failed ==="

    if ($SaveAll) { $dte.ExecuteCommand('File.SaveAll'); "=== Saved all ===" }
}
finally {
    if ($dte) { $dte.Quit() }
    [MessageFilter]::Revoke()
}
exit [int]($failed -ne 0)
