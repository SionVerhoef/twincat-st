<#
Tests for scripts/xae_edit.ps1 that need no XAE. CI runs them on windows-latest under Windows
PowerShell 5.1, the only PowerShell the script supports.

  * the pure helpers it decides with: argument checks, line endings, readback comparison, the
    graphical-body and file-object tests, tree paths, fingerprints and the state file
  * input files: UTF-8 with or without a BOM and UTF-16 with one read the same; anything else,
    a BOM in front of cp1252 text included, is refused rather than written into a POU as U+FFFD
  * the guards, on fake tree items: the build guard finds unsaved POUs and fails closed on one it
    cannot read; a POU the user typed in after the tool's edit is refused; -Force goes ahead once
    and never makes the user's edits pass as the tool's own afterwards; typing in a method of a
    saved POU, which XAE keeps in a member document, counts as unsaved; the build guard lists an
    unsaved document of a file its walk did not report
  * CreateChild on fake tree items: a vInfo form XAE refuses is followed by the next one, and an
    error with the object created anyway stops instead of creating it twice
  * the script itself, run as a child process: its argument errors exit 2, 'list' with no XAE
    exits 0 (so the C# interop compiles and the ROT enumerates; skipped while an XAE runs), and a
    solution no XAE holds exits 2 with the advice to open it

Everything that needs an XAE is in evals/field-test-xae-edit.md.

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\xae_edit_tests.ps1
#>
$xaeEdit = Join-Path (Split-Path $PSScriptRoot) 'scripts\xae_edit.ps1'
. $xaeEdit
$ErrorActionPreference = 'Continue'

$failures = New-Object Collections.ArrayList
function Check([string] $label, [bool] $ok, [string] $detail = '') {
    if ($ok) { [Console]::Out.WriteLine("ok    $label") }
    else {
        [Console]::Out.WriteLine("FAIL  $label")
        if ($detail) { [Console]::Out.WriteLine("        $detail") }
        [void] $failures.Add($label)
    }
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("xae_edit_tests_" + [Guid]::NewGuid().ToString('N'))
[void] (New-Item -ItemType Directory -Path $tmp)
$body = Join-Path $tmp 'body.st'
Set-Content -LiteralPath $body -Value 'x := 1;' -Encoding Ascii

# --- arguments ----------------------------------------------------------------
$ok = @{ Solution = 'x.sln'; TreePath = 'TIPC^PLC1'; Part = 'impl'; FromFile = $body; Out = 'o.st'; Name = 'M_New'; Returns = 'LREAL' }
Check 'list needs nothing' ((Get-ArgumentError 'list' @{}) -eq '')
Check 'an unknown command is refused' ((Get-ArgumentError 'frobnicate' $ok) -like 'unknown command*')
Check 'every other command needs -Solution' ((Get-ArgumentError 'show' @{}) -like '*-Solution*')
Check 'show defaults its tree path' ((Get-ArgumentError 'show' @{ Solution = 'x.sln' }) -eq '')
Check 'build needs no tree path' ((Get-ArgumentError 'build' @{ Solution = 'x.sln' }) -eq '')
foreach ($c in 'get', 'set', 'new', 'add-method', 'add-property', 'save') {
    $a = $ok.Clone(); $a.Remove('TreePath')
    Check "$c needs a tree path" ((Get-ArgumentError $c $a) -like '*tree path*')
}
$a = $ok.Clone(); $a.Remove('Out')
Check 'get needs -Out: stdout would go through the console code page' ((Get-ArgumentError 'get' $a) -like '*-Out*')
$a = $ok.Clone(); $a.Remove('Part')
Check 'set needs -Part: no default part to overwrite by mistake' ((Get-ArgumentError 'set' $a) -like '*-Part*')
$a = $ok.Clone(); $a.Remove('FromFile')
Check 'set needs -FromFile' ((Get-ArgumentError 'set' $a) -like '*-FromFile*')
$a = $ok.Clone(); $a.FromFile = (Join-Path $tmp 'missing.st')
Check 'a missing input file is named' ((Get-ArgumentError 'set' $a) -like 'no such file*')
$a = $ok.Clone(); $a.Name = '1st'
Check 'add-method refuses a name that is no identifier' ((Get-ArgumentError 'add-method' $a) -like '*-Name*')
Check 'a complete set passes' ((Get-ArgumentError 'set' $ok) -eq '')
$a = $ok.Clone(); $a.Remove('Returns')
Check 'add-property needs -Returns, the type of the property' ((Get-ArgumentError 'add-property' $a) -like '*-Returns*')
$a = $ok.Clone(); $a.Returns = "INT;`r`nEND_VAR"
Check '-Returns takes one type, not a fragment of code' ((Get-ArgumentError 'add-method' $a) -like '-Returns takes one type*')
$a = $ok.Clone(); $a.Type = 'gvl'; $a.FromImpl = $body
Check 'new refuses a body for an object that has none' ((Get-ArgumentError 'new' $a) -like '*has no body*')
$a.Type = 'fun'
Check 'new takes a body for a function' ((Get-ArgumentError 'new' $a) -eq '')
Check 'every -Type has a CreateChild code' (@('fb', 'prg', 'fun', 'dut', 'enum', 'union', 'alias', 'gvl', 'itf' |
    Where-Object { -not $script:NewTypes[$_] }).Count -eq 0)
Check "an alias's base type comes from its declaration" (
    ((Get-AliasBase "TYPE T_Mm : LREAL;`r`nEND_TYPE" '') -ceq 'LREAL') -and
    ((Get-AliasBase "TYPE T_Mm : LREAL := 1.5;`nEND_TYPE" '') -ceq 'LREAL') -and
    ((Get-AliasBase "TYPE T_Buf :`n    ARRAY[0..9] OF BYTE;`nEND_TYPE" '') -ceq 'ARRAY[0..9] OF BYTE'))
Check '... or from -Returns without one' (((Get-AliasBase $null 'UDINT') -ceq 'UDINT') -and -not (Get-AliasBase '' ''))
Check 'a vInfo form is printed with its type' (((Format-VInfo $null) -eq 'null') -and
    ((Format-VInfo 1) -eq 'Int32 1') -and ((Format-VInfo ([string[]] @('1', 'INT'))) -eq 'String[] [1, INT]'))

Check 'identifiers' ((Test-Identifier 'M_Reset') -and (Test-Identifier '_x1') -and -not (Test-Identifier '1x') -and
                     -not (Test-Identifier 'a b') -and -not (Test-Identifier "M_X`n") -and -not (Test-Identifier ''))

# --- line endings and readback ------------------------------------------------
Check 'LF to CRLF' ((ConvertTo-Eol "a`nb`n" "`r`n") -ceq "a`r`nb`r`n")
Check 'mixed to CRLF, no doubled CR' ((ConvertTo-Eol "a`r`nb`nc`rd" "`r`n") -ceq "a`r`nb`r`nc`r`nd")
Check 'CRLF to LF' ((ConvertTo-Eol "a`r`nb" "`n") -ceq "a`nb")
Check 'a CRLF text is replaced in CRLF' ((Get-Eol "a`r`nb") -ceq "`r`n")
Check 'an LF text is replaced in LF' ((Get-Eol "a`nb") -ceq "`n")
Check 'a one-line or empty text gets CRLF, as XAE writes' (((Get-Eol 'a') -ceq "`r`n") -and ((Get-Eol '') -ceq "`r`n"))
Check 'readback: line endings do not count' (Test-SameText "a`r`nb`r`n" "a`nb")
Check 'readback: trailing line breaks do not count' (Test-SameText "a`r`nb" "a`r`nb`r`n`r`n")
Check 'readback: case counts' (-not (Test-SameText 'nCount := 1;' 'ncount := 1;'))
Check 'readback: a changed line counts' (-not (Test-SameText "a`nb" "a`nc"))
Check 'readback: trailing spaces count' (-not (Test-SameText 'a ' 'a'))
Check 'the first difference is named by line' ((Get-FirstDifference "a`nb`nc" "a`nX`nc") -eq "line 2: set 'b', read back 'X'")
Check 'a missing line reads (end)' ((Get-FirstDifference "a`nb" 'a') -eq "line 2: set 'b', read back '(end)'")

# --- body, file and path tests ------------------------------------------------
Check 'an LD body is XML' (Test-XmlBody '<NWL><Networks /></NWL>')
Check 'a CFC body after blank lines is XML' (Test-XmlBody "`r`n  <CFC>")
Check 'ST with a comparison is not XML' (-not (Test-XmlBody "IF a < b THEN`r`n  c := 1;`r`nEND_IF"))
Check 'an empty body is not XML' (-not (Test-XmlBody ''))
Check 'a POU file is a file object' (Test-ObjectFileName 'C:\src\Line1\PLC1\POUs\FB_X.TcPOU')
Check 'a GVL and a DUT are file objects' ((Test-ObjectFileName 'GVL_Io.TcGVL') -and (Test-ObjectFileName 'E_State.TcDUT'))
Check "a method's file name is not" (-not (Test-ObjectFileName 'C:\src\POUs\FB_X.TcPOU;FB_X.M_Reset'))
Check 'nor is a method whose name starts Tc' (-not (Test-ObjectFileName 'C:\src\POUs\FB_X.TcPOU;FB_X.TcpSend'))
Check 'a folder is not' (-not (Test-ObjectFileName 'C:\src\Line1\PLC1\POUs'))
Check 'the parent of a method is its POU' ((Get-ParentPath 'TIPC^PLC1^PLC1 Project^POUs^FB_X^M_Reset') -eq 'TIPC^PLC1^PLC1 Project^POUs^FB_X')
Check 'the root has no parent' ((Get-ParentPath 'TIPC') -eq '')

# --- fingerprints and the state file ------------------------------------------
$f1 = Get-Fingerprint @('FB_X', 'FUNCTION_BLOCK FB_X', 'x := 1;')
Check 'a fingerprint is stable' ($f1 -eq (Get-Fingerprint @('FB_X', 'FUNCTION_BLOCK FB_X', 'x := 1;')))
Check 'a fingerprint sees a one-character edit' ($f1 -ne (Get-Fingerprint @('FB_X', 'FUNCTION_BLOCK FB_X', 'x := 2;')))
Check 'a fingerprint keeps parts apart' ((Get-Fingerprint @('ab', 'c')) -ne (Get-Fingerprint @('a', 'bc')))
Check 'a fingerprint is SHA-256 hex' ($f1 -match '^[0-9a-f]{64}$')

$sp = Get-StatePath 'C:\src\Line1\Line1.sln'
Check 'the state file lives in TEMP, not beside the solution' ($sp.StartsWith([IO.Path]::GetTempPath()))
Check 'the state file does not depend on path case' ($sp -eq (Get-StatePath 'c:\SRC\line1\LINE1.sln'))
Check 'each solution has its own state file' ($sp -ne (Get-StatePath 'C:\src\Line2\Line2.sln'))

$sf = Join-Path $tmp 'state.txt'
Check 'no state file reads as empty' ((Read-EditState $sf 42).Count -eq 0)
$m = @{ 'TIPC^PLC1^PLC1 Project^POUs^FB_X' = $f1; 'TIPC^PLC1^PLC1 Project^POUs^Sub Folder^FB_Y' = 'ab' * 32 }
Write-EditState $sf 42 $m
$back = Read-EditState $sf 42
Check 'the state round trips, spaces and carets in paths included' (
    $back.Count -eq 2 -and $back['TIPC^PLC1^PLC1 Project^POUs^FB_X'] -eq $f1 -and
    $back['TIPC^PLC1^PLC1 Project^POUs^Sub Folder^FB_Y'] -eq ('ab' * 32))
Check 'state lookups ignore case, as tree paths do' ($back['tipc^plc1^plc1 project^pous^fb_x'] -eq $f1)
Check 'another XAE process voids the state' ((Read-EditState $sf 43).Count -eq 0)
Write-EditState $sf 42 @{}
Check 'an emptied state reads as empty' ((Read-EditState $sf 42).Count -eq 0)

# --- input and output files ---------------------------------------------------
$text = "// Fl$([char]0xE4)che in mm$([char]0xB2)`r`nx := 1;`r`n"
$variants = @{
    'utf8-nobom.st' = (New-Object Text.UTF8Encoding $false).GetBytes($text)
    'utf8-bom.st'   = [byte[]] (0xEF, 0xBB, 0xBF) + (New-Object Text.UTF8Encoding $false).GetBytes($text)
    'utf16-bom.st'  = [byte[]] (0xFF, 0xFE) + [Text.Encoding]::Unicode.GetBytes($text)
}
foreach ($k in $variants.Keys) {
    $p = Join-Path $tmp $k
    [IO.File]::WriteAllBytes($p, $variants[$k])
    $r = Read-SourceFile $p
    Check "$k reads as the same text, without a BOM character" ($r -ceq $text) ([string] $r)
}
$ansi = Join-Path $tmp 'cp1252.st'
[IO.File]::WriteAllBytes($ansi, [byte[]] (0x2F, 0x2F, 0x20, 0x6D, 0x6D, 0xB2))
$threw = $false
try { [void] (Read-SourceFile $ansi) } catch { $threw = $true }
Check 'a cp1252 file is refused, not read as U+FFFD' $threw
$bomAnsi = Join-Path $tmp 'bom-cp1252.st'
[IO.File]::WriteAllBytes($bomAnsi, [byte[]] (0xEF, 0xBB, 0xBF, 0x2F, 0x2F, 0x20, 0xB2))
$threw = $false
try { [void] (Read-SourceFile $bomAnsi) } catch { $threw = $true }
Check 'a UTF-8 BOM in front of cp1252 text is refused too' $threw

Push-Location $tmp
try { Write-Utf8File 'out.st' $text } finally { Pop-Location }
$bytes = [IO.File]::ReadAllBytes((Join-Path $tmp 'out.st'))
Check "-Out resolves against PowerShell's location, not the process directory" ($bytes.Length -gt 0)
Check '-Out writes UTF-8 without a BOM' ($bytes[0] -ne 0xEF -and [Text.Encoding]::UTF8.GetString($bytes) -ceq $text)

# --- the guards, against fake tree items --------------------------------------
# A fake answers what the script asks a TwinCAT tree item: Name, the two texts, ChildCount,
# Child(i), and VSProjectItem.Saved / FileNames(1). $file = $null: no VSProjectItem at all.
function New-Fake([string] $name, $file, $saved, [string] $decl = '', [string] $impl = '', [object[]] $kids = @()) {
    $pi = $null
    if ($null -ne $file) {
        $pi = New-Object psobject -Property @{ Saved = $saved; File = $file }
        $pi | Add-Member ScriptMethod FileNames { param($i) $this.File }
    }
    $o = New-Object psobject -Property @{ Name = $name; VSProjectItem = $pi; DeclarationText = $decl
                                          ImplementationText = $impl; Kids = $kids; ChildCount = $kids.Count }
    $o | Add-Member ScriptMethod Child { param($i) $this.Kids[$i - 1] }
    $o
}

Initialize-Interop
Check 'this test process shows no dialog (window enumeration runs)' ([XaeWindows]::Blocking($PID) -eq '')

$m1 = New-Fake 'M_X' 'C:\p\FB_A.TcPOU;FB_A.M_X' $null 'METHOD M_X' 'M_X := TRUE;'
$fbA = New-Fake 'FB_A' 'C:\p\FB_A.TcPOU' $false 'FUNCTION_BLOCK FB_A' 'x := 1;' @($m1)
$fbB = New-Fake 'FB_B' 'C:\p\FB_B.TcPOU' $true
$fbT = New-Fake 'FB_T' 'C:\p\FB_T.TcPOU' $true '' '' @((New-Fake 'TcpSend' 'C:\p\FB_T.TcPOU;FB_T.TcpSend' $null))
$fbU = New-Fake 'FB_U' $null $null '' '' @((New-Fake 'M_Y' 'C:\p\FB_U.TcPOU;FB_U.M_Y' $null))
$fbO = New-Fake 'FB_O' 'C:\p\FB_O.TcPOU' 'yes'
$root = New-Fake 'PLC1 Project' '' $null '' '' @((New-Fake 'POUs' 'C:\p' $true '' '' @($fbA, $fbB, $fbT, $fbU, $fbO)))
$found = @(Find-Unsaved $root 'TIPC^PLC1^PLC1 Project')
$seen = @($found | ForEach-Object { "$($_.Path -replace '^.*\^', '')=$($_.Unreadable)" }) -join ' '
Check 'the build guard finds the unsaved POU, and counts unreadable ones as not its own' (
    $seen -eq 'FB_A=False FB_U=True FB_O=True') $seen

# Stop-Edit exits the process; here it throws, so a refusal can be checked.
function Stop-Edit([int] $code, [string] $message) { throw "STOP $code $message" }
function Test-Guard($owner) { try { Assert-OwnerClean $owner; 'passed' } catch { $_.Exception.Message } }
$script:Xae = @{ Pid = $PID }; $script:StateFile = Join-Path $tmp 'guard.txt'; $script:State = @{}; $script:Forced = @{}
$owner = @{ Item = $fbA; Path = 'TIPC^PLC1^PLC1 Project^POUs^FB_A' }
Check 'unsaved edits nobody recorded are refused' ((Test-Guard $owner) -like 'STOP 1 refused*')
Update-OwnerState $owner
Check "the tool's own recorded edit goes ahead" ((Test-Guard $owner) -eq 'passed')
Check 'and is kept in the state file' ((Read-EditState $script:StateFile $PID).Count -eq 1)
$m1.ImplementationText = 'M_X := FALSE; (* typed by the user *)'
Check "typing in another part of the POU after the tool's edit is refused" ((Test-Guard $owner) -like 'STOP 1*')
$Force = $true
Check '-Force goes ahead' ((Test-Guard $owner) -eq 'passed')
Update-OwnerState $owner
$Force = $false
Check "after -Force, the user's edits never pass as the tool's own" (
    (Test-Guard $owner) -like 'STOP 1*' -and (Read-EditState $script:StateFile $PID).Count -eq 0)
$fbA.VSProjectItem.Saved = $true
Check 'a saved POU with no unsaved member document goes ahead' ((Test-Guard $owner) -eq 'passed')

# Typing in a method leaves the POU's own Saved at True; XAE marks a document '<file>;<POU>.<member>'
# instead (field run 2026-10-29). The guard has to see it, or set overwrites the typing.
$doc = New-Object psobject -Property @{ FullName = 'C:\p\FB_A.TcPOU;FB_A.M_X'; Saved = $false }
$other = New-Object psobject -Property @{ FullName = 'C:\p\FB_AB.TcPOU;FB_AB.M_X'; Saved = $false }
$script:Xae = @{ Pid = $PID; Dte = @{ Documents = @($doc, $other) } }
$m1.ImplementationText = 'M_X := TRUE; (* typed after a save *)'
Check "an unsaved member document makes a saved POU unsaved" (-not (Test-OwnerSaved $fbA))
Check "typing in a method of a saved POU is refused" ((Test-Guard $owner) -like 'STOP 1 refused*')
$found = @(Find-Unsaved $root 'TIPC^PLC1^PLC1 Project')
Check 'the build guard finds a POU whose method alone is unsaved' (
    @($found | Where-Object { $_.Path -like '*^FB_A' -and -not $_.Unreadable }).Count -eq 1)
# A cycle-time change shows only as the document PlcTask.TcTTO; whether the walk reaches the task
# is not measured, so the document must be listed unless the walk reported its file.
$task = New-Object psobject -Property @{ FullName = 'C:\p\PlcTask.TcTTO'; Saved = $false }
$script:Xae.Dte.Documents = @($doc, $task)
$docs = @(Get-UnsavedDocuments @{ 'c:\P\fb_a.TcPOU' = $true })
Check "the build guard lists an unsaved PLC file it did not report, not a reported POU's method" (
    $docs.Count -eq 1 -and $docs[0] -eq 'C:\p\PlcTask.TcTTO') ($docs -join ', ')
$script:Xae.Dte.Documents = @($doc, $other)
$doc.Saved = $true
Check "another POU's document whose name starts the same does not count" (Test-OwnerSaved $fbA)
$script:Xae = @{ Pid = $PID }

# CreateChild: Beckhoff's documented vInfo forms disagree, so the tool tries them in turn.
$pous = New-Fake 'POUs' 'C:\p' $true
$pous | Add-Member ScriptMethod CreateChild {
    param($n, $code, $before, $v)
    if ($v -is [string[]]) { throw 'Type mismatch' }
    $c = New-Fake $n "C:\p\$n.TcPOU" $true
    $this.Kids = @($this.Kids) + $c; $this.ChildCount = $this.Kids.Count
    $c
}
$forms = @(); $forms += , ([string[]] @('1', 'INT')); $forms += , ([object[]] @(1, 'INT'))
$made = New-TreeChild @{ Item = $pous; Path = 'TIPC^PLC1^PLC1 Project^POUs' } 'F_Calc' 603 $forms
Check 'a vInfo form XAE refuses is followed by the next one' (
    $made.Path -eq 'TIPC^PLC1^PLC1 Project^POUs^F_Calc' -and $pous.ChildCount -eq 1)
$duts = New-Fake 'DUTs' 'C:\p' $true
$duts | Add-Member ScriptMethod CreateChild {
    param($n, $code, $before, $v)
    $this.Kids = @($this.Kids) + (New-Fake $n "C:\p\$n.TcDUT" $true); $this.ChildCount = $this.Kids.Count
    throw 'Unspecified error'
}
$forms = @(); $forms += , $null; $forms += ''
function Test-Create($t, $n, $code, $forms) { try { [void] (New-TreeChild $t $n $code $forms); 'passed' } catch { $_.Exception.Message } }
$r = Test-Create @{ Item = $duts; Path = 'TIPC^PLC1^PLC1 Project^DUTs' } 'ST_A' 606 $forms
Check 'an error with the object created anyway stops, rather than creating it twice' (
    $r -like 'STOP 1*anyway*' -and $duts.ChildCount -eq 1) $r

# --- the script as a child process --------------------------------------------
function Invoke-Child([string[]] $argv) {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = (Get-Process -Id $PID).Path
    $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$xaeEdit`" " + (($argv | ForEach-Object { "`"$_`"" }) -join ' ')
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $p = [Diagnostics.Process]::Start($psi)
    $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
    $p.WaitForExit()
    @{ Code = $p.ExitCode; Out = $o.Result; Err = $e.Result }
}

$r = Invoke-Child @()
Check 'no command: exit 2 and the usage' ($r.Code -eq 2 -and $r.Err -like '*usage:*') "exit $($r.Code): $($r.Err)"
$r = Invoke-Child @('set', 'TIPC^PLC1', '-Solution', 'x.sln', '-FromFile', $body)
Check 'set without -Part: exit 2 before touching XAE' ($r.Code -eq 2 -and $r.Err -like '*-Part*') "exit $($r.Code): $($r.Err)"
$running = @(Get-Process TcXaeShell, devenv -ErrorAction SilentlyContinue)
if ($running) { [Console]::Out.WriteLine("skip  list with no XAE: an XAE or Visual Studio is running (PID $($running[0].Id))") }
else {
    $r = Invoke-Child @('list')
    Check "list with no XAE: exit 0 and says so (the interop compiles, the ROT enumerates)" (
        $r.Code -eq 0 -and $r.Out -like '*no XAE*') "exit $($r.Code): $($r.Out) $($r.Err)"
}
$r = Invoke-Child @('show', '-Solution', (Join-Path $tmp 'missing.sln'))
Check 'a missing solution file: exit 2' ($r.Code -eq 2 -and $r.Err -like '*no such solution*') "exit $($r.Code): $($r.Err)"
$sln = Join-Path $tmp 'Line1.sln'
Set-Content -LiteralPath $sln -Value '' -Encoding Ascii
$r = Invoke-Child @('show', '-Solution', $sln)
Check 'a solution no XAE holds: exit 2, pointing to tcpou.py and xae_build.ps1' (
    $r.Code -eq 2 -and $r.Err -like '*no XAE holds*' -and $r.Err -like '*tcpou.py*') "exit $($r.Code): $($r.Err)"

Remove-Item -LiteralPath $tmp -Recurse -Force

[Console]::Out.WriteLine('')
if ($failures.Count) { [Console]::Out.WriteLine("$($failures.Count) failed"); exit 1 }
[Console]::Out.WriteLine('all checks passed')
exit 0
