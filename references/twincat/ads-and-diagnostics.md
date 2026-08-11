# ADS and Diagnostics

Reading a running TwinCAT system, and triaging one that is not running. **TwinCAT-specific** — ADS is Beckhoff's protocol; CODESYS systems typically expose OPC UA instead (see `../codesys.md`).

Scope note: this is the triage layer — enough to diagnose a machine that is not behaving. It is not a full treatment of motion, communications or testing, and does not try to be.

> **Read-only by default.** Writing a variable, activating a configuration, or changing Run/Config mode on a real controller changes machine behaviour. Propose the command; let the human run it. See `SKILL.md` rule 2.

## ADS in one page

- **AMS NetID** — the address of a TwinCAT device, six bytes: `5.1.2.3.1.1`. Conventionally the IPv4 address plus `.1.1`, but it is independent of the IP and can be anything.
- **AMS port** — which service on that device. Common ones:

  | Port | Service |
  |---|---|
  | `851` | PLC runtime 1 — **the one you almost always want** |
  | `852` / `853` | PLC runtime 2 / 3 |
  | `500` | NC PTP |
  | `10000` | System Service |

  Other services have their own ports; look them up rather than guessing.

- **Transport** — AMS/TCP on **48898**. Broadcast route discovery uses UDP **48899**.
- **Routes** — ADS needs a route configured **on both ends**. This is the usual cause of "connection refused" / ADS error 1861 (timeout). Static routes live in `StaticRoutes.xml`:
  - Windows: `C:\TwinCAT\3.1\Target\StaticRoutes.xml`
  - TwinCAT/BSD: `/usr/local/etc/TwinCAT/3.1/Target/StaticRoutes.xml`

## Reading from a client (`pyads`)

**Establish which host you are on before writing any of this.** `pyads` presents one API over three different ADS stacks, and the routing half behaves differently on each. Windows is the common case — XAE runs there, so the engineering laptop usually is a Windows machine with TwinCAT installed.

| | **Windows** (TwinCAT installed) | **Linux** | **TwinCAT/BSD** |
|---|---|---|---|
| Library loaded | `TcAdsDll.dll`, from the TwinCAT installation | bundled `AdsLib.so` | `libTcAdsDll.so` |
| AMS router | the TwinCAT **router service** | in-process, inside the library | system router |
| Local AmsNetId | assigned by the router | you set it yourself | assigned by the system |
| Adding a route | **not through `pyads`** — see below | `pyads.add_route_to_plc(...)` | system configuration |
| Needs TwinCAT installed? | **yes** | no | n/a |

The consequential difference, and the one that produces a confusing failure: **the route-management calls raise on Windows.** `add_route`, `add_route_to_plc` and `delete_route` are guarded, and on Win32 they raise

```
RuntimeError: Router interface is not available on Win32 systems.
              Configure AMS routes using the TwinCAT router service.
```

That is by design — the Windows router is a separate service that owns the route table, so pyads refuses rather than pretending. Copying a Linux snippet onto a Windows machine therefore fails at the routing line, not at the connection, which sends people looking in the wrong place.

### Windows

The route already exists, or you add it outside Python: in XAE under **SYSTEM → Routes**, via the TwinCAT tray icon → **Router → Edit Routes**, with the `TcXaeMgmt` PowerShell module (`Add-AdsRoute`), or by editing `StaticRoutes.xml`. Then connecting needs no IP, because the local router resolves the AmsNetId from its own table:

```python
import pyads

# The local router resolves this AmsNetId via its route table.
plc = pyads.Connection('5.1.2.3.1.1', pyads.PORT_TC3PLC1)   # 851
plc.open()
...
plc.close()
```

For the runtime on the same machine, use the local address rather than hardcoding one:

```python
plc = pyads.Connection(pyads.get_local_address().netid, pyads.PORT_TC3PLC1)
```

### Linux

No system router, so the library keeps the route table in-process: declare who you are, then add the route at both ends.

```python
import pyads

pyads.open_port()
pyads.set_local_address('192.168.1.50.1.1')   # this machine's AmsNetId

# Writes a route into the PLC's own table — needs its credentials.
pyads.add_route_to_plc(
    sending_net_id='192.168.1.50.1.1',
    adding_host_name='192.168.1.50',
    ip_address='192.168.1.10',                # the PLC
    username='Administrator',
    password='1',
    route_name='linux-client')

plc = pyads.Connection('5.1.2.3.1.1', pyads.PORT_TC3PLC1, '192.168.1.10')
plc.open()
```

`add_route_to_plc` **modifies the controller's route table and needs its credentials** — a human action, not an agent action. Propose it; don't run it.

An AmsNetId is conventionally the host's IP with `.1.1` appended, but it is an identifier rather than an address: it does not have to match, and on a machine with several interfaces it often does not. Read the real one rather than deriving it.

### Reading, on any platform

Once connected the API is identical:

```python
state = plc.read_by_name('MAIN.fbStation.eState', pyads.PLCTYPE_INT)
pos   = plc.read_by_name('MAIN.stAxis.NcToPlc.ActPos', pyads.PLCTYPE_LREAL)
```

**The highest-value use is symbol introspection, not value reading.** Dumping the symbol table gives you the real variable names, types and structure of the machine you are writing code for, which beats inferring them from partial source:

```python
for sym in plc.get_all_symbols():
    print(sym.name, sym.symbol_type)
```

Other clients: `TwinCAT.Ads` (.NET, cross-platform), `TcXaeMgmt` (PowerShell — route management, and the easiest way to add a Windows route from a script), `ADSREAD`/`ADSWRITE` in `Tc2_System` for PLC-to-PLC.

> Platform behaviour above was read from the pyads source rather than exercised — there is no PLC or TwinCAT installation here to connect to. Treat the code as the right shape, not as a tested recipe.

## EtherCAT triage

The EtherCAT state machine: `INIT (1)` → `PREOP (2)` → `SAFEOP (4)` → `OP (8)`. **`OP` is the only healthy steady state.** A slave stuck in `SAFEOP` is the single most common "my I/O doesn't work" report — outputs are held at zero in `SAFEOP`, inputs still update, so the machine looks half-alive.

Signals to read first, in this order:

| Signal | Healthy | Meaning when not |
|---|---|---|
| `Device x (EtherCAT).WcState` (per slave) | `0` | Working counter mismatch — slave missing, not responding, or a cable/topology fault |
| `Device x (EtherCAT).InfoData.State` (per slave) | `8` (OP) | Slave is not operational; low nibble is the AL state, higher bits flag link/presence problems |
| `Device x (EtherCAT).DevState` (master) | `0` | Master-level fault — link down, slave count mismatch, frame loss |
| **AL Status Code** (per slave, in the IDE) | — | The actual reason a slave refused to reach OP |

**Look the AL Status Code up** in the Beckhoff documentation or the slave vendor's manual — do not guess at a meaning from the number. Common categories are configuration mismatch (the ESI/PDO mapping does not match the physical device), distributed-clock/sync errors, and watchdog timeouts, but the specific code matters.

Triage order that resolves most cases:

1. **Is it in OP?** If not, read the AL Status Code — it usually names the problem directly.
2. **Does the configured topology match the physical one?** Scan the boxes in the IDE and compare. A swapped or added terminal invalidates the process image.
3. **Is the ESI file present and the right revision?** A revision mismatch between the configured and actual device is a classic SAFEOP blocker.
4. **Is the task actually running,** at the cycle time you think, without overruns? Check the real-time node for exceeded cycles and jitter.
5. **Only then look at the PLC code.**

## Runtime and task health

- **Cycle exceeded / watchdog** — the program did not return in time. Almost always a loop (Rule 3) or heavy work in a fast task. Check real-time utilisation and jitter, not just the code.
- **Run vs Config mode** — a PLC in Config mode runs nothing. "Nothing happens and there are no errors" is often this.
- **7-day trial licence expired** (4024) — regenerate on the target and restart into Run. Fits the "worked last week, dead now" pattern.
- **Boot project missing** — the controller comes back from a power cycle with no program. The project must be explicitly activated as a boot project.
- **`Tc3_EventLogger`** is the right place for operator-facing alarms; the ADS logger and Scope View (TE1300 for the professional version) are the right tools for timing and signal traces.

## TcUnit

Open-source unit-test framework for TwinCAT ([tcunit.org](https://www.tcunit.org)), the practical way to get a real verification loop.

- Test suites are function blocks extending `FB_TestSuite`, containing test methods; a `PRG` runs them in a task.
- Results are reported to the TwinCAT error list — and are readable over ADS, which is what lets an agent close the loop without a human relaying output.
- `TcUnit-Runner` drives builds headlessly via the TwinCAT Automation Interface (COM/DTE) on a Windows machine, for CI.
- Keep test suites in a `Tests/` folder, excluded from the release build.

Design for testability: a device FB whose only contact with the outside world is its interface can be tested with a simulated input; one that reads a GVL directly cannot.
