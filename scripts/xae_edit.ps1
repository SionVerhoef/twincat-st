<#
Edit, save and build PLC objects through the XAE the user already has open, so XAE never asks to
reload a file. It finds that XAE in the Running Object Table by the solution it holds and edits
through the Automation Interface: the edit lands in XAE's memory, the open editor shows it at once
with an unsaved *, and the file changes only when XAE saves it. It never starts an XAE, never logs
in and never activates. With XAE closed, use tcpou.py and xae_build.ps1 instead.

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_edit.ps1 <command> [<TreePath>] -Solution <x.sln> [options]

  list                                                 every XAE: PID, solution, open dialogs. Run it first
  show       [<TreePath>]                              type, language, file, unsaved state, children (default TIPC)
  get        <TreePath> [-Part decl|impl] -Out <file>  write the text XAE holds to a UTF-8 file (LD/CFC: XML)
  set        <TreePath> -Part decl|impl -FromFile <f>  replace it in XAE's memory, then read it back. impl: ST only
  new        <FolderPath> -Type <t> -Name X [-Lang st|ld] [-Returns T] [-FromDecl f] [-FromImpl f]
                                                       a new object; XAE writes its file and registers it.
                                                       -Type fb (default), prg, fun, dut (struct), enum,
                                                       union, alias, gvl, itf (interface)
  add-method <PouPath> -Name M_X [-Returns T] [-FromDecl f] [-FromImpl f]   a new method in a POU or interface
  add-property <PouPath> -Name P -Returns T [-FromDecl f] [-NoSet]  a new property with Get (and Set) accessors
  save       <TreePath>                                save that object's file (a method saves its POU). Never Save All
  build                                                build in this XAE and print the compiler output

  An accessor is a tree path too: set '<PouPath>^Speed^Get' -Part impl -FromFile get.st

  -Force           set, add-method, add-property, save: go ahead although the POU holds unsaved edits
                   this tool did not make. set replaces the whole part, so those edits in that part are lost
  -SaveUserEdits   build: go ahead although it will save unsaved edits this tool did not make
  -PublicAssemblies '<IDE>\PublicAssemblies'   build: where envdte.dll lives for this XAE

A tree path looks like 'TIPC^PLC1^PLC1 Project^POUs^FB_X^M_Reset'; quote it.
Exit code: 0 = done; 1 = failed, refused, a readback mismatch, a failed build, or an unexpected
error (printed as 'failed: ...'); 2 = could not run, nothing written: bad arguments, no such .sln,
no XAE or several hold it, XAE shows a dialog or did not answer, no TwinCAT PLC project, no
envdte.dll, or the wrong PowerShell.
Needs Windows PowerShell 5.1 (powershell.exe), run at the same elevation as XAE.
See references/twincat/xae-automation.md.
#>
param(
    [Parameter(Position = 0)] [string] $Command = '',
    [Parameter(Position = 1)] [string] $TreePath = '',
    [string] $Solution = '',
    [ValidateSet('decl', 'impl')] [string] $Part = '',
    [string] $Out = '',
    [string] $FromFile = '',
    [string] $Name = '',
    [string] $FromDecl = '',
    [string] $FromImpl = '',
    [ValidateSet('st', 'ld')] [string] $Lang = 'st',
    [ValidateSet('fb', 'prg', 'fun', 'dut', 'enum', 'union', 'alias', 'gvl', 'itf')] [string] $Type = 'fb',
    [string] $Returns = '',
    [switch] $NoSet,
    [switch] $Force,
    [switch] $SaveUserEdits,
    [string] $PublicAssemblies = 'C:\Program Files (x86)\Beckhoff\TcXaeShell\Common7\IDE\PublicAssemblies'
)
$ErrorActionPreference = 'Stop'

$script:Commands = @('list', 'show', 'get', 'set', 'new', 'add-method', 'add-property', 'save', 'build')
$script:Forced = @{}    # owners this run went ahead on with -Force: never recorded as its own
$script:Usage = 'usage: xae_edit.ps1 list | show|get|set|new|add-method|add-property|save <TreePath> -Solution <x.sln> | build -Solution <x.sln>  (see the header of xae_edit.ps1)'

# CreateChild sub types, from Beckhoff's Automation Interface table "Creating PLC objects". Only
# 604 (function block) and 609 (method) have been measured; the field run checks the rest.
$script:NewTypes = @{ prg = 602; fun = 603; fb = 604; enum = 605; dut = 606; union = 607; alias = 623; gvl = 615; itf = 618 }
$script:ItfType = 618

# --- Pure helpers: no XAE, no COM. tests/xae_edit_tests.ps1 dot-sources this file for them. ---

function Get-ArgumentError([string] $cmd, [hashtable] $a) {
    if ($cmd -notin $script:Commands) { return "unknown command '$cmd'" }
    if ($cmd -eq 'list') { return '' }
    if (-not $a.Solution) { return '-Solution <x.sln> is required' }
    if (($cmd -in @('get', 'set', 'new', 'add-method', 'add-property', 'save')) -and -not $a.TreePath) { return "$cmd needs a tree path" }
    if ($cmd -eq 'get' -and -not $a.Out) { return 'get needs -Out <file>' }
    if ($cmd -eq 'set' -and -not $a.Part) { return 'set needs -Part decl or -Part impl' }
    if ($cmd -eq 'set' -and -not $a.FromFile) { return 'set needs -FromFile <file>' }
    if (($cmd -in @('new', 'add-method', 'add-property')) -and -not (Test-Identifier $a.Name)) { return "$cmd needs -Name, an identifier such as M_Reset or FB_Pump" }
    if ($cmd -eq 'add-property' -and -not $a.Returns) { return 'add-property needs -Returns <type>, the type of the property' }
    if ($a.Returns -match '[\r\n;]') { return '-Returns takes one type, such as LREAL or ARRAY[0..9] OF INT' }
    if ($cmd -eq 'new' -and $a.FromImpl -and $a.Type -notin @('fb', 'prg', 'fun')) { return "a $($a.Type) has no body: -FromImpl is for fb, prg and fun" }
    foreach ($f in $a.FromFile, $a.FromDecl, $a.FromImpl) {
        if ($f -and -not (Test-Path -LiteralPath $f -PathType Leaf)) { return "no such file: $f" }
    }
    ''
}

function Test-Identifier([string] $name) { $name -match '^[A-Za-z_][A-Za-z0-9_]*\z' }

function Format-VInfo($v) {
    if ($null -eq $v) { 'null' }
    elseif ($v -is [array]) { "$($v.GetType().Name) [$($v -join ', ')]" }
    else { "$($v.GetType().Name) $v" }
}

# Graphical bodies (LD, FBD, CFC) come back as XmlArchive XML; Structured Text never starts with '<'.
function Test-XmlBody([string] $text) { $text -match '^\s*<' }

# A file-level object's VSProjectItem names its file; a method's names '<file>;<POU>.<method>',
# which can end like a file too (FB_X.TcPOU;FB_X.TcpSend).
function Test-ObjectFileName([string] $file) { $file -notmatch ';' -and $file -match '\.Tc[A-Za-z]+\z' }

function Get-ParentPath([string] $path) {
    $i = $path.LastIndexOf('^')
    if ($i -lt 0) { '' } else { $path.Substring(0, $i) }
}

function ConvertTo-Eol([string] $text, [string] $eol) {
    $text.Replace("`r`n", "`n").Replace("`r", "`n").Replace("`n", $eol)
}

# The line ending to write: whatever the text being replaced uses. XAE's own files are CRLF.
function Get-Eol([string] $text) {
    if ($text.Contains("`r`n")) { "`r`n" } elseif ($text.Contains("`n")) { "`n" } else { "`r`n" }
}

function Get-Lines([string] $text) { (ConvertTo-Eol $text "`n").TrimEnd([char] 10).Split([char] 10) }

# Equal apart from line endings and trailing line breaks. Case counts: -ceq, not -eq.
function Test-SameText([string] $a, [string] $b) {
    ((Get-Lines $a) -join "`n") -ceq ((Get-Lines $b) -join "`n")
}

function Get-FirstDifference([string] $a, [string] $b) {
    $x = @(Get-Lines $a); $y = @(Get-Lines $b)
    for ($i = 0; $i -lt [Math]::Max($x.Count, $y.Count); $i++) {
        $l = if ($i -lt $x.Count) { $x[$i] } else { '(end)' }
        $r = if ($i -lt $y.Count) { $y[$i] } else { '(end)' }
        if ($l -cne $r) { return "line $($i + 1): set '$l', read back '$r'" }
    }
    'none'
}

function Get-Fingerprint([string[]] $texts) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $bytes = [Text.Encoding]::UTF8.GetBytes((@($texts) | ForEach-Object { "$_" }) -join "`0")
    -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
}

# .NET resolves a relative path against the process directory, not PowerShell's location.
function Resolve-FullPath([string] $path) {
    $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($path)
}

# UTF-8 with or without a BOM, or UTF-16 with one. Anything else is refused rather than
# written into the POU as U+FFFD. The BOM is read here, not by ReadAllText: on a UTF-8 BOM that
# swaps in a decoder that never refuses.
function Read-SourceFile([string] $path) {
    $b = [IO.File]::ReadAllBytes((Resolve-FullPath $path))
    $skip = 0
    $enc = New-Object Text.UTF8Encoding -ArgumentList $false, $true
    if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) { $skip = 3 }
    elseif ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) { $skip = 2; $enc = New-Object Text.UnicodeEncoding -ArgumentList $false, $false, $true }
    elseif ($b.Length -ge 2 -and $b[0] -eq 0xFE -and $b[1] -eq 0xFF) { $skip = 2; $enc = New-Object Text.UnicodeEncoding -ArgumentList $true, $false, $true }
    try { $enc.GetString($b, $skip, $b.Length - $skip) }
    catch { throw "$path is not UTF-8 (or UTF-16 with a BOM); save it as UTF-8" }
}

function Write-Utf8File([string] $path, [string] $text) {
    [IO.File]::WriteAllText((Resolve-FullPath $path), $text, (New-Object Text.UTF8Encoding $false))
}

# Which unsaved POUs this tool dirtied, as a fingerprint of their whole text taken after its last
# write. One file per solution in %TEMP%; it is void once XAE restarts, since the PID changes.
function Get-StatePath([string] $solution) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $hash = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($solution.ToLowerInvariant()))
    $tag = -join ($hash[0..7] | ForEach-Object { $_.ToString('x2') })
    Join-Path ([IO.Path]::GetTempPath()) "twincat-st-xae_edit-$tag.txt"
}

function Read-EditState([string] $file, [int] $xaePid) {
    $map = @{}    # case-insensitive, as tree paths are
    if (-not (Test-Path -LiteralPath $file)) { return $map }
    $lines = [IO.File]::ReadAllLines($file, [Text.Encoding]::UTF8)
    if ($lines.Count -eq 0 -or $lines[0] -ne "pid $xaePid") { return $map }
    foreach ($line in ($lines | Select-Object -Skip 1)) {
        $i = $line.IndexOf("`t")
        if ($i -gt 0) { $map[$line.Substring($i + 1)] = $line.Substring(0, $i) }
    }
    $map
}

function Write-EditState([string] $file, [int] $xaePid, [hashtable] $map) {
    $lines = @("pid $xaePid") + @($map.Keys | Sort-Object | ForEach-Object { "$($map[$_])`t$_" })
    [IO.File]::WriteAllLines($file, [string[]] $lines, (New-Object Text.UTF8Encoding $false))
}

# --- XAE plumbing ---

function Say([string] $text) { [Console]::Out.WriteLine($text) }

# Not Write-Error: under $ErrorActionPreference = 'Stop' it throws a full error record instead.
function Stop-Edit([int] $code, [string] $message) {
    [Console]::Error.WriteLine($message)
    exit $code
}

function Initialize-Interop {
    Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
[ComImport, Guid("00000016-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IOleMessageFilter {
    [PreserveSig] int HandleInComingCall(int t, IntPtr h, int ti, IntPtr i);
    [PreserveSig] int RetryRejectedCall(IntPtr h, int ti, int r);
    [PreserveSig] int MessagePending(IntPtr h, int ti, int p);
}
// XAE rejects every call while a modal dialog is open. Retrying forever hangs, so retry for
// TimeoutMs, then give up and count it: a call given up on can come back empty, not as an error.
public class XaeFilter : IOleMessageFilter {
    [DllImport("Ole32.dll")] static extern int CoRegisterMessageFilter(IOleMessageFilter n, out IOleMessageFilter o);
    public static int TimeoutMs = 30000;
    public static int Rejected = 0;
    public static void Register() { IOleMessageFilter o; CoRegisterMessageFilter(new XaeFilter(), out o); }
    public static void Revoke()   { IOleMessageFilter o; CoRegisterMessageFilter(null, out o); }
    int IOleMessageFilter.HandleInComingCall(int t, IntPtr h, int ti, IntPtr i) { return 0; }
    int IOleMessageFilter.RetryRejectedCall(IntPtr h, int ti, int r) {
        if (r == 2 && ti < TimeoutMs) return 200;
        Rejected++;
        return -1;
    }
    int IOleMessageFilter.MessagePending(IntPtr h, int ti, int p) { return 2; }
}
public class RotEntry { public string Name; public object Obj; }
public static class Rot {
    [DllImport("ole32.dll")] static extern int GetRunningObjectTable(int r, out IRunningObjectTable t);
    [DllImport("ole32.dll")] static extern int CreateBindCtx(int r, out IBindCtx c);
    public static List<RotEntry> List(string[] prefixes) {
        var res = new List<RotEntry>();
        IRunningObjectTable rot; GetRunningObjectTable(0, out rot);
        IEnumMoniker en; rot.EnumRunning(out en);
        IMoniker[] m = new IMoniker[1];
        while (en.Next(1, m, IntPtr.Zero) == 0) {
            try {
                IBindCtx ctx; CreateBindCtx(0, out ctx);
                string name; m[0].GetDisplayName(ctx, null, out name);
                bool wanted = false;
                foreach (string p in prefixes) if (name.StartsWith(p, StringComparison.OrdinalIgnoreCase)) wanted = true;
                if (!wanted) continue;
                object o; rot.GetObject(m[0], out o);
                res.Add(new RotEntry { Name = name, Obj = o });
            } catch (Exception) { }
        }
        return res;
    }
}
public static class XaeWindows {
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    static string Describe(IntPtr h, string cls) {
        var t = new StringBuilder(512); GetWindowText(h, t, 512);
        var sb = new StringBuilder("[" + cls + "] '" + t + "'");
        EnumChildWindows(h, (ch, l) => {
            var ct = new StringBuilder(2048); GetWindowText(ch, ct, 2048);
            if (ct.Length > 0 && IsWindowVisible(ch)) sb.Append(" | " + ct.ToString().Replace("\r", " ").Replace("\n", " "));
            return true; }, IntPtr.Zero);
        return sb.ToString();
    }
    // The dialogs blocking this process, with their texts, or "" when none. A modal dialog
    // disables the unowned window it belongs to, and a message box has class #32770; a floating
    // tool window does neither, so it does not count. Which window is "main" is not asked:
    // .NET can pick the message box itself. Win32 only, so it works while COM is blocked.
    public static string Blocking(int pid) {
        bool disabled = false;
        var boxes = new List<string>(); var owned = new List<string>();
        EnumWindows((h, l) => {
            uint p; GetWindowThreadProcessId(h, out p);
            if (p != (uint)pid || !IsWindowVisible(h)) return true;
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            bool unowned = GetWindow(h, 4) == IntPtr.Zero;    // GW_OWNER
            if (unowned && !IsWindowEnabled(h)) disabled = true;
            if (c.ToString() == "#32770") boxes.Add(Describe(h, c.ToString()));
            else if (!unowned) owned.Add(Describe(h, c.ToString()));
            return true; }, IntPtr.Zero);
        if (disabled) boxes.AddRange(owned);
        if (disabled && boxes.Count == 0) boxes.Add("(its window is disabled, as behind a modal dialog, but no dialog is visible)");
        return string.Join(Environment.NewLine, boxes.ToArray());
    }
}
"@
}

# From PowerShell, late-bound DTE reads the Error List as empty; early-bound EnvDTE from XAE's own
# PublicAssemblies reads it (as in xae_build.ps1). Loaded for build only.
function Initialize-ErrorReader {
    [void][Reflection.Assembly]::LoadFrom("$PublicAssemblies\envdte.dll")
    [void][Reflection.Assembly]::LoadFrom("$PublicAssemblies\envdte80.dll")
    Add-Type -ReferencedAssemblies "$PublicAssemblies\envdte.dll", "$PublicAssemblies\envdte80.dll" -TypeDefinition @"
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
}

function Get-Blocking([int] $xaePid) {
    if (-not (Get-Process -Id $xaePid -ErrorAction SilentlyContinue)) { return "process $xaePid has exited" }
    [XaeWindows]::Blocking($xaePid)
}

# Before every write: no dialog now, and every read the write rests on was answered.
function Assert-NoDialog {
    Assert-Answered 'reading what this write depends on'
    $d = Get-Blocking $script:Xae.Pid
    if ($d) { Stop-Edit 2 "XAE (PID $($script:Xae.Pid)) shows a dialog, so this stopped before writing anything more. Ask the user to answer it, then run this again:`n$d" }
}

function Assert-Answered([string] $what) {
    if ([XaeFilter]::Rejected -gt 0) {
        Stop-Edit 2 "XAE did not answer while ${what}: it rejected the call, or stayed busy for 30 s. A dialog may be open; 'xae_edit.ps1 list' shows it."
    }
}

# Every XAE in the Running Object Table. Dialogs are read through Win32 first, because a COM call
# into an XAE that shows one is rejected until the dialog closes.
function Get-XaeInstances {
    foreach ($e in [Rot]::List([string[]] @('!TcXaeShell.DTE.', '!VisualStudio.DTE.'))) {
        $xaePid = 0
        [void][int]::TryParse(($e.Name -replace '^.*:', ''), [ref] $xaePid)
        $blocking = Get-Blocking $xaePid
        $sln = $null
        if (-not $blocking) {
            [XaeFilter]::Rejected = 0
            try { $sln = [string] $e.Obj.Solution.FullName } catch { $blocking = "could not be asked for its solution: $($_.Exception.Message)" }
            if ([XaeFilter]::Rejected) { $blocking = 'did not answer (busy for 30 s, or it rejected the call)' }
        }
        [pscustomobject]@{ Rot = $e.Name.TrimStart('!'); Pid = $xaePid; Solution = $sln; Blocking = $blocking; Dte = $e.Obj }
    }
}

# An XAE missing from the ROT runs at another integrity level, elevated where this shell is not or
# the other way round: the ROT is separate per level. Or it is still starting.
function Get-UnlistedHint($instances) {
    $seen = @($instances | ForEach-Object { $_.Pid })
    $missing = @(Get-Process -Name TcXaeShell, devenv -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $seen })
    if (-not $missing) { return '' }
    "XAE process $(($missing | ForEach-Object { $_.Id }) -join ', ') is not in this shell's Running Object Table: it runs as administrator and this shell does not, or the other way round, or it is still starting. Run both at the same level."
}

function Connect-Xae([string] $sln) {
    if (-not (Test-Path -LiteralPath $sln -PathType Leaf)) { Stop-Edit 2 "no such solution file: $sln" }
    $full = (Resolve-Path -LiteralPath $sln).ProviderPath    # .Path carries a provider prefix on a UNC path
    $all = @(Get-XaeInstances)
    $hits = @($all | Where-Object { $_.Solution -eq $full })
    if ($hits.Count -gt 1) {
        Stop-Edit 2 "$($hits.Count) XAE instances hold $full (PIDs $(($hits | ForEach-Object { $_.Pid }) -join ', ')). Ask the user to close all but their own; a hidden one may be left over from xae_build.ps1."
    }
    if ($hits.Count -eq 0) {
        # An XAE that could not be asked may be the one holding it: send nobody to disk edits then.
        $blocked = @($all | Where-Object { $_.Blocking })
        if ($blocked) {
            $msg = "could not tell which XAE holds ${full}. Ask the user to answer what XAE shows, then run this again:"
            foreach ($b in $blocked) { $msg += "`nXAE PID $($b.Pid): $($b.Blocking)" }
            Stop-Edit 2 $msg
        }
        $msg = "no XAE holds $full. Ask the user to open it in XAE, or, with XAE closed, use tcpou.py and xae_build.ps1."
        $hint = Get-UnlistedHint $all
        if ($hint) { $msg += "`n$hint" }
        Stop-Edit 2 $msg
    }
    $script:Xae = $hits[0]
    [XaeFilter]::Rejected = 0    # another XAE may have been busy while it was asked
    $script:Sms = New-Object Collections.ArrayList
    $projects = $script:Xae.Dte.Solution.Projects
    for ($i = 1; $i -le $projects.Count; $i++) {
        $sm = $null
        try { $sm = $projects.Item($i).Object; [void] $sm.LookupTreeItem('TIPC') } catch { $sm = $null }
        if ($null -ne $sm) { [void] $script:Sms.Add($sm) }
    }
    Assert-Answered 'opening the solution'
    if ($script:Sms.Count -eq 0) { Stop-Edit 2 "$full holds no TwinCAT project with a PLC" }
    $script:StateFile = Get-StatePath $full
    $script:State = Read-EditState $script:StateFile $script:Xae.Pid
}

# Tree items are returned inside a hashtable: PowerShell unrolls an enumerable COM object written
# to the pipeline, and a tree item enumerates its children.
function Find-TreeItem([string] $path) {
    $found = New-Object Collections.ArrayList
    foreach ($sm in $script:Sms) {
        $it = $null
        try { $it = $sm.LookupTreeItem($path) } catch { }
        if ($null -ne $it) { [void] $found.Add(@{ Sm = $sm; Item = $it; Path = $path }) }
    }
    Assert-Answered "looking up $path"
    if ($found.Count -gt 1) { Stop-Edit 1 "$path exists in $($found.Count) TwinCAT projects of this solution, and this tool cannot tell them apart. Edit it in XAE." }
    if ($found.Count -eq 1) { return $found[0] }
    # Name what does exist, so the next try is not a guess.
    for ($p = Get-ParentPath $path; $p; $p = Get-ParentPath $p) {
        foreach ($sm in $script:Sms) {
            $it = $null
            try { $it = $sm.LookupTreeItem($p) } catch { }
            if ($null -ne $it) {
                $names = @(for ($i = 1; $i -le $it.ChildCount; $i++) { $it.Child($i).Name })
                Stop-Edit 1 "no tree item $path. $p holds: $($names -join ', ')"
            }
        }
    }
    Stop-Edit 1 "no tree item $path. Paths start 'TIPC^<PLC>^<PLC> Project'; 'show' lists what is there."
}

function Get-PartText($item, [string] $part) {
    try { if ($part -eq 'decl') { $item.DeclarationText } else { $item.ImplementationText } } catch { $null }
}

function Set-PartText($item, [string] $part, [string] $text) {
    if ($part -eq 'decl') { $item.DeclarationText = $text } else { $item.ImplementationText = $text }
}

function Get-Language($item) { try { $l = $item.Language; if ($null -ne $l) { [int] $l } } catch { } }

function Get-FileName($item) { try { [string] $item.VSProjectItem.FileNames(1) } catch { '' } }

function Get-Saved($item) {
    try { $s = $item.VSProjectItem.Saved; if ($s -is [bool]) { return $s } } catch { }
    $null
}

# A POU, DUT, GVL or interface: an object with its own file, which XAE saves as one.
function Test-FileObject($item) { ((Get-Saved $item) -is [bool]) -and (Test-ObjectFileName (Get-FileName $item)) }

# The file-level object a path lives in: the POU for a method, the path itself for a POU.
function Get-Owner($sm, [string] $path) {
    for ($p = $path; $p; $p = Get-ParentPath $p) {
        $it = $null
        try { $it = $sm.LookupTreeItem($p) } catch { }
        if ($null -ne $it -and (Test-FileObject $it)) { return @{ Item = $it; Path = $p } }
    }
    $null
}

function Get-ItemTexts($item) {
    [string] $item.Name
    [string] (Get-PartText $item 'decl')
    [string] (Get-PartText $item 'impl')
    $n = $item.ChildCount
    for ($i = 1; $i -le $n; $i++) { $c = $item.Child($i); Get-ItemTexts $c }
}

function Get-OwnerFingerprint($item) {
    $fp = Get-Fingerprint @(Get-ItemTexts $item)
    Assert-Answered 'reading the POU'
    $fp
}

# Unsaved edits in the owner that this tool did not make are the user's: refuse to write over
# them, or to save them, unless -Force.
function Assert-OwnerClean($owner) {
    if (Get-Saved $owner.Item) { return }
    if ($script:State[$owner.Path] -eq (Get-OwnerFingerprint $owner.Item)) { return }
    if ($Force) {
        Say "warning: $($owner.Path) holds unsaved edits this tool did not make; going ahead (-Force)"
        $script:Forced[$owner.Path] = $true
        return
    }
    Stop-Edit 1 "refused: $($owner.Path) holds unsaved edits this tool did not make, probably typed in XAE. Ask the user to save or undo them. -Force goes ahead anyway: set replaces the whole part, edits in it included, and save writes them all to disk."
}

# Remember the owner's text as this tool's own, so its next write or save goes ahead. Not after
# -Force: the user's edits are in that text too, and must not pass as this tool's next time.
function Update-OwnerState($owner) {
    if ((Get-Saved $owner.Item) -or $script:Forced[$owner.Path]) { $script:State.Remove($owner.Path) }
    else { $script:State[$owner.Path] = Get-OwnerFingerprint $owner.Item }
    Write-EditState $script:StateFile $script:Xae.Pid $script:State
}

function Get-RequiredOwner($t) {
    $owner = Get-Owner $t.Sm $t.Path
    if (-not $owner) { Stop-Edit 1 "no POU, DUT, GVL or interface file holds $($t.Path)" }
    $owner
}

# Set one part, then read it back. Written in the line endings the replaced text uses. A failure
# after the call still records the owner: whatever XAE now holds there, this tool put it there.
function Write-Part($owner, $item, [string] $path, [string] $part, [string] $text) {
    Assert-NoDialog
    $text = ConvertTo-Eol $text (Get-Eol (Get-PartText $item $part))
    $failure = ''
    try { Set-PartText $item $part $text } catch { $failure = "XAE refused the $part of ${path}: $($_.Exception.Message)" }
    Assert-Answered "setting the $part of $path"
    if (-not $failure) {
        $back = Get-PartText $item $part
        Assert-Answered "reading back the $part of $path"
        if (-not (Test-SameText $text $back)) {
            $failure = "the $part of $path reads back differently from what was set, $(Get-FirstDifference $text $back). XAE holds the read-back text, unsaved; check it in the editor."
        }
    }
    if ($failure) { Update-OwnerState $owner; Stop-Edit 1 $failure }
}

function Test-HasChild($item, [string] $name) {
    $n = $item.ChildCount
    for ($i = 1; $i -le $n; $i++) { if ($item.Child($i).Name -ieq $name) { return $true } }
    $false
}

# Unsaved file-level objects under a PLC project, as @{ Item; Path; Unreadable }. Folders are
# walked; an object's own children (methods, properties) live in its file and are not. An object
# whose saved state cannot be read is reported too, as someone else's: the guard fails closed.
function Find-Unsaved($item, [string] $path) {
    $n = $item.ChildCount
    for ($i = 1; $i -le $n; $i++) {
        $c = $item.Child($i)
        $p = "$path^$($c.Name)"
        $file = Get-FileName $c
        # A method here means $item was an object whose own file name could not be read.
        if ($file.Contains(';')) { @{ Item = $item; Path = $path; Unreadable = $true }; return }
        if (Test-ObjectFileName $file) {
            $s = Get-Saved $c
            if ($s -isnot [bool]) { @{ Item = $c; Path = $p; Unreadable = $true } }
            elseif (-not $s) { @{ Item = $c; Path = $p; Unreadable = $false } }
        }
        else { Find-Unsaved $c $p }
    }
}

function Get-UnsavedObjects {
    $roots = 0
    foreach ($sm in $script:Sms) {
        $tipc = $sm.LookupTreeItem('TIPC')
        $nPlc = $tipc.ChildCount
        for ($i = 1; $i -le $nPlc; $i++) {
            $plc = $tipc.Child($i)
            $nProj = $plc.ChildCount
            for ($j = 1; $j -le $nProj; $j++) {
                $proj = $plc.Child($j)
                if ($proj.Name -notlike '* Project') { continue }
                $roots++
                Find-Unsaved $proj "TIPC^$($plc.Name)^$($proj.Name)"
            }
        }
    }
    Assert-Answered 'looking for unsaved objects'
    if ($roots -eq 0 -and -not $SaveUserEdits) {
        Stop-Edit 2 "found no 'TIPC^<PLC>^<PLC> Project' node, so cannot check what the build would save. Pass -SaveUserEdits to build anyway."
    }
}

# Unsaved open documents other than PLC objects, which the tree walk covers: a build saves those
# too, an I/O or task editor of the .tsproj for one.
function Get-UnsavedDocuments {
    foreach ($d in $script:Xae.Dte.Documents) {
        $f = ''; $s = $true
        try { $f = [string] $d.FullName; $s = $d.Saved } catch { }
        if ($s -eq $false -and -not (Test-ObjectFileName ($f -split ';')[0])) { $f }
    }
    Assert-Answered 'listing open documents'
}

function Remove-SavedState {
    foreach ($k in @($script:State.Keys)) {
        $it = $null
        foreach ($sm in $script:Sms) { try { $it = $sm.LookupTreeItem($k) } catch { }; if ($null -ne $it) { break } }
        if ($null -eq $it -or (Get-Saved $it)) { $script:State.Remove($k) }
    }
    Write-EditState $script:StateFile $script:Xae.Pid $script:State
}

# --- Commands ---

function Invoke-List {
    $all = @(Get-XaeInstances)
    if (-not $all) { Say 'no XAE in the Running Object Table' }
    foreach ($x in $all) {
        $what = if ($x.Blocking) { "dialog: $($x.Blocking -replace "`r?`n", "`n    ")" } elseif ($x.Solution) { $x.Solution } else { '(no solution open)' }
        Say "PID $($x.Pid)  $($x.Rot -replace ':\d+$', '')  $what"
    }
    $hint = Get-UnlistedHint $all
    if ($hint) { Say $hint }
}

function Invoke-Show {
    $t = Find-TreeItem $(if ($TreePath) { $TreePath } else { 'TIPC' })
    $it = $t.Item
    $lang = Get-Language $it
    $langName = if ($lang -eq 1) { ' (ST)' } elseif ($lang -eq 6) { ' (LD)' } else { '' }
    Say $t.Path
    Say "  type      $($it.ItemType)"
    if ($null -ne $lang) { Say "  language  $lang$langName" }
    $owner = Get-Owner $t.Sm $t.Path
    if ($owner) {
        Say "  file      $(Get-FileName $owner.Item)"
        $saved = Get-Saved $owner.Item
        $by = if ($saved) { '' } elseif ($script:State[$owner.Path] -eq (Get-OwnerFingerprint $owner.Item)) { ', edited by this tool' } else { ', edited by someone else' }
        $of = if ($owner.Path -ne $t.Path) { " (its file object $($owner.Path))" } else { '' }
        Say "  saved     $saved$by$of"
    }
    $n = $it.ChildCount
    for ($i = 1; $i -le $n; $i++) { $c = $it.Child($i); Say "  ^$($c.Name)  type $($c.ItemType)" }
    Assert-Answered "reading $($t.Path)"
}

function Invoke-Get {
    $t = Find-TreeItem $TreePath
    $p = if ($Part) { $Part } else { 'impl' }
    $text = Get-PartText $t.Item $p
    Assert-Answered "reading the $p of $($t.Path)"
    if ($null -eq $text) { Stop-Edit 1 "$($t.Path) has no $p part" }
    Write-Utf8File $Out (ConvertTo-Eol $text "`n")
    $note = if (Test-XmlBody $text) { ' (a graphical body: XML, which set refuses)' } else { '' }
    Say "wrote the $p of $($t.Path) to $(Resolve-FullPath $Out)$note"
}

function Invoke-Set {
    $t = Find-TreeItem $TreePath
    $current = Get-PartText $t.Item $Part
    Assert-Answered "reading the $Part of $($t.Path)"
    if ($null -eq $current) { Stop-Edit 1 "$($t.Path) has no $Part part" }
    # Language codes after Beckhoff's Automation Interface (2 IL, 3 SFC, 4 FBD, 5 CFC, 6 LD); only
    # 1 = ST and 6 = LD have been seen in the field. An XML body is graphical whatever its code.
    $lang = Get-Language $t.Item
    if ($Part -eq 'impl' -and ((Test-XmlBody $current) -or ($lang -ge 2 -and $lang -le 6))) {
        Stop-Edit 1 "refused: the body of $($t.Path) is not Structured Text (language $lang), and this tool sets Structured Text only. Edit it in XAE."
    }
    $text = Read-SourceFile $FromFile
    if (Test-XmlBody $text) { Stop-Edit 1 "refused: $FromFile holds XML, not Structured Text" }
    $owner = Get-RequiredOwner $t
    Assert-OwnerClean $owner
    Write-Part $owner $t.Item $t.Path $Part $text
    Update-OwnerState $owner
    Say "set the $Part of $($t.Path) in XAE (unsaved; the file changes on: xae_edit.ps1 save)"
}

function Get-ItemType($item) { try { [int] $item.ItemType } catch { 0 } }

# CreateChild with the first vInfo form XAE accepts, each tried only while the child does not
# exist yet. Beckhoff's table and its own samples disagree on some forms, and only the function
# block's and the method's were measured, so the form that worked is printed: the field run keeps
# that one. Returns the new item inside a hashtable, which the pipeline does not unroll.
function New-TreeChild($t, [string] $name, [int] $code, [object[]] $forms) {
    $errors = @()
    for ($i = 0; $i -lt $forms.Count; $i++) {
        Assert-NoDialog
        $child = $null
        try { $child = $t.Item.CreateChild($name, $code, '', $forms[$i]) } catch { $errors += "vInfo $(Format-VInfo $forms[$i]): $($_.Exception.Message)" }
        Assert-Answered "creating $name"
        if ($null -ne $child) {
            if ($forms.Count -gt 1) { Say "  created with vInfo form $($i + 1) of $($forms.Count): $(Format-VInfo $forms[$i])" }
            return @{ Sm = $t.Sm; Item = $child; Path = "$($t.Path)^$name" }
        }
        if (Test-HasChild $t.Item $name) { Stop-Edit 1 "XAE reported an error but created $name in $($t.Path) anyway; check it in XAE. $($errors -join '; ')" }
    }
    Stop-Edit 1 "XAE did not create $name (type $code) in $($t.Path): $($errors -join '; ')"
}

function Invoke-New {
    $t = Find-TreeItem $TreePath
    $decl = if ($FromDecl) { Read-SourceFile $FromDecl } else { $null }
    $impl = if ($FromImpl) { Read-SourceFile $FromImpl } else { $null }
    if ((Test-XmlBody $decl) -or (Test-XmlBody $impl)) { Stop-Edit 1 'refused: XML is not Structured Text' }
    if (Test-HasChild $t.Item $Name) { Stop-Edit 1 "refused: $($t.Path) already has $Name" }
    $lang = (@{ st = 1; ld = 6 })[$Lang]
    $ret = if ($Returns) { $Returns } else { 'BOOL' }
    $forms = @()
    if ($Type -in @('fb', 'prg')) { $forms += $lang }
    elseif ($Type -eq 'fun') { $forms += , ([string[]] @("$lang", $ret)); $forms += , ([object[]] @($lang, $ret)) }
    else { $forms += , $null }
    $obj = New-TreeChild $t $Name $script:NewTypes[$Type] $forms
    if ($null -ne $decl) { Write-Part $obj $obj.Item $obj.Path 'decl' $decl }
    if ($null -ne $impl) { Write-Part $obj $obj.Item $obj.Path 'impl' $impl }
    Update-OwnerState $obj
    $state = if (Get-Saved $obj.Item) { 'saved' } else { 'unsaved; the file changes on: xae_edit.ps1 save' }
    Say "added $Type $($obj.Path) as $(Get-FileName $obj.Item) ($state). XAE registers it in the .plcproj itself"
}

# A method of a POU (609, measured) or of an interface (610, from Beckhoff's table).
function Invoke-AddMethod {
    $t = Find-TreeItem $TreePath
    $decl = if ($FromDecl) { Read-SourceFile $FromDecl } elseif ($Returns) { "METHOD $Name : $Returns`r`n" } else { $null }
    $impl = if ($FromImpl) { Read-SourceFile $FromImpl } else { $null }
    if ((Test-XmlBody $decl) -or (Test-XmlBody $impl)) { Stop-Edit 1 'refused: XML is not Structured Text' }
    if (Test-HasChild $t.Item $Name) { Stop-Edit 1 "refused: $($t.Path) already has $Name" }
    $itf = (Get-ItemType $t.Item) -eq $script:ItfType
    if ($itf -and $null -ne $impl) { Stop-Edit 1 'refused: an interface method has no body, so -FromImpl does not apply' }
    $owner = Get-RequiredOwner $t
    Assert-OwnerClean $owner
    $forms = @()
    if (-not $itf) { $forms += , $null }
    elseif ($Returns) { $forms += $Returns; $forms += , ([string[]] @($Returns)) }
    else { $forms += , $null; $forms += '' }
    $m = New-TreeChild $t $Name $(if ($itf) { 610 } else { 609 }) $forms
    Update-OwnerState $owner
    if ($null -ne $decl) { Write-Part $owner $m.Item $m.Path 'decl' $decl }
    if ($null -ne $impl) { Write-Part $owner $m.Item $m.Path 'impl' $impl }
    Update-OwnerState $owner
    Say "added method $($m.Path) in XAE (unsaved; the file changes on: xae_edit.ps1 save)"
}

# A property (611; 612 in an interface) with its Get and, unless -NoSet, its Set accessor. XAE's
# editor adds both with a new property; whether CreateChild does is not known, so the tool adds
# whichever is missing (613/614; 654/655 in an interface) and removes Set for -NoSet.
function Invoke-AddProperty {
    $t = Find-TreeItem $TreePath
    $decl = if ($FromDecl) { Read-SourceFile $FromDecl } else { $null }
    if (Test-XmlBody $decl) { Stop-Edit 1 'refused: XML is not Structured Text' }
    if (Test-HasChild $t.Item $Name) { Stop-Edit 1 "refused: $($t.Path) already has $Name" }
    $itf = (Get-ItemType $t.Item) -eq $script:ItfType
    $owner = Get-RequiredOwner $t
    Assert-OwnerClean $owner
    $forms = @()
    if ($itf) { $forms += $Returns; $forms += , ([string[]] @($Returns)) }
    else { $forms += , ([string[]] @('1', $Returns)); $forms += , ([object[]] @(1, $Returns)) }
    $p = New-TreeChild $t $Name $(if ($itf) { 612 } else { 611 }) $forms
    Update-OwnerState $owner
    $codes = if ($itf) { @{ Get = 654; Set = 655 } } else { @{ Get = 613; Set = 614 } }
    foreach ($acc in 'Get', 'Set') {
        $has = Test-HasChild $p.Item $acc
        if ($acc -eq 'Set' -and $NoSet) {
            if ($has) {
                Assert-NoDialog
                try { $p.Item.DeleteChild('Set') } catch { Stop-Edit 1 "XAE did not remove the Set accessor of $($p.Path): $($_.Exception.Message). Delete it in XAE." }
                Assert-Answered "removing the Set accessor of $($p.Path)"
                Say '  removed the Set accessor XAE added (-NoSet)'
            }
            continue
        }
        if (-not $has) { [void] (New-TreeChild $p $acc $codes[$acc] @(, $null)); Say "  added the $acc accessor" }
    }
    Update-OwnerState $owner
    if ($null -ne $decl) { Write-Part $owner $p.Item $p.Path 'decl' $decl }
    Update-OwnerState $owner
    $kids = @(for ($i = 1; $i -le $p.Item.ChildCount; $i++) { $p.Item.Child($i).Name })
    Say "added property $($p.Path) with $($kids -join ', ') in XAE (unsaved; the file changes on: xae_edit.ps1 save). Bodies: set '$($p.Path)^Get' -Part impl"
}

function Invoke-Save {
    $t = Find-TreeItem $TreePath
    $owner = Get-RequiredOwner $t
    $file = Get-FileName $owner.Item
    if (Get-Saved $owner.Item) { Update-OwnerState $owner; Say "nothing to save: $file is up to date"; return }
    Assert-OwnerClean $owner
    Assert-NoDialog
    try { $owner.Item.VSProjectItem.Save() } catch { Stop-Edit 1 "XAE did not save $($owner.Path): $($_.Exception.Message)" }
    Assert-Answered "saving $($owner.Path)"
    if (-not (Get-Saved $owner.Item)) { Stop-Edit 1 "XAE still reports $($owner.Path) unsaved" }
    Update-OwnerState $owner
    Say "saved $($owner.Path) to $file"
}

# A build saves every unsaved object first, the user's half-typed edits included. So this lists
# them, refuses on any it did not make, and saves the PLC objects itself, one by one, before it
# builds: then XAE's own "before building" setting has none of them left to save or ask about.
function Invoke-Build {
    if (-not (Test-Path -LiteralPath "$PublicAssemblies\envdte.dll")) {
        Stop-Edit 2 "envdte.dll not found in '$PublicAssemblies'. Pass -PublicAssemblies for this XAE install."
    }
    Initialize-ErrorReader
    $mine = New-Object Collections.ArrayList; $theirs = New-Object Collections.ArrayList
    foreach ($u in @(Get-UnsavedObjects)) {
        if (-not $u.Unreadable -and $script:State[$u.Path] -eq (Get-OwnerFingerprint $u.Item)) { [void] $mine.Add($u) }
        else { [void] $theirs.Add($u) }
    }
    $docs = @(Get-UnsavedDocuments)
    $named = @($theirs | ForEach-Object { if ($_.Unreadable) { "$($_.Path) (its saved state could not be read)" } else { $_.Path } }) + $docs
    if ($named.Count -and -not $SaveUserEdits) {
        Stop-Edit 1 "refused: a build saves every unsaved object, and these hold edits this tool did not make:`n  $($named -join "`n  ")`nAsk the user to save or undo them, or pass -SaveUserEdits."
    }
    foreach ($u in @($mine) + @($theirs)) {
        if ($u.Unreadable) { Say "left to the build's own save: $($u.Path)"; continue }
        Assert-NoDialog
        try { $u.Item.VSProjectItem.Save() } catch { Stop-Edit 1 "XAE did not save $($u.Path): $($_.Exception.Message)" }
        Assert-Answered "saving $($u.Path)"
        Say "saved $($u.Path)"
    }
    foreach ($d in $docs) { Say "left to the build's own save: $d" }
    Remove-SavedState
    Assert-NoDialog
    $sb = $script:Xae.Dte.Solution.SolutionBuild
    $sb.Build($true)
    Assert-Answered 'building'
    Start-Sleep -Seconds 2    # let the Error List catch up
    Say '=== Build pane ==='
    Say ([XaeDump]::Pane($script:Xae.Dte, 'Build'))
    Say '=== Error List (compiler) ==='
    Say ([XaeDump]::Errors($script:Xae.Dte, $true))
    $failed = $sb.LastBuildInfo
    Say "=== Projects failed: $failed ==="
    Remove-SavedState
    if ($failed -ne 0) { exit 1 }
}

function Invoke-XaeEdit {
    $err = Get-ArgumentError $Command @{ TreePath = $TreePath; Solution = $Solution; Part = $Part; Out = $Out
                                         FromFile = $FromFile; Name = $Name; FromDecl = $FromDecl; FromImpl = $FromImpl
                                         Type = $Type; Returns = $Returns }
    if ($err) { Stop-Edit 2 "$err`n$script:Usage" }
    if ($PSVersionTable.PSEdition -ne 'Desktop') { Stop-Edit 2 'needs Windows PowerShell 5.1: run it with powershell.exe, not pwsh' }
    if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') { Stop-Edit 2 'needs a single-threaded apartment: run powershell.exe without -MTA' }
    Initialize-Interop
    [XaeFilter]::Register()
    try {
        if ($Command -eq 'list') { Invoke-List; return }
        Connect-Xae $Solution
        Assert-NoDialog
        switch ($Command) {
            'show'         { Invoke-Show }
            'get'          { Invoke-Get }
            'set'          { Invoke-Set }
            'new'          { Invoke-New }
            'add-method'   { Invoke-AddMethod }
            'add-property' { Invoke-AddProperty }
            'save'         { Invoke-Save }
            'build'        { Invoke-Build }
        }
    }
    finally { [XaeFilter]::Revoke() }
}

# Dot-sourced by the tests: define the functions only.
if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-XaeEdit }
    catch { [Console]::Error.WriteLine("failed: $($_.Exception.Message)"); exit 1 }
    exit 0
}
