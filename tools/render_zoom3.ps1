param(
    [Parameter(Mandatory=$true)][string]$CacheDirectory,
    [Parameter(Mandatory=$true)][string]$KeyFile,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$DependencyDirectory,
    [Parameter(Mandatory=$true)][string]$ClassesDirectory
)
$ErrorActionPreference = 'Stop'
# DependencyDirectory is Gradle's modules-2/files-2.1 directory. No cache/key files are copied.
$libraries = @(
    'net.runelite/cache/1.12.39', 'com.google.guava/guava/23.2-jre',
    'com.google.code.gson/gson/2.10.1', 'org.slf4j/slf4j-api/1.7.25',
    'org.apache.commons/commons-compress/1.10', 'org.antlr/antlr4-runtime/4.13.1',
    'net.java.dev.jna/jna/5.9.0', 'commons-cli/commons-cli/1.3.1',
    'org.projectlombok/lombok/1.18.30'
)
$rendererJars = foreach ($library in $libraries) {
    $matches = @(Get-ChildItem -LiteralPath (Join-Path $DependencyDirectory $library) -Filter '*.jar' -Recurse |
        Where-Object Name -NotMatch 'sources|javadoc')
    if ($matches.Count -ne 1) { throw "Expected one binary JAR for $library" }
    $matches[0].FullName
}
$rendererClasspath = $rendererJars -join [IO.Path]::PathSeparator
& javac --release 11 -cp $rendererClasspath -d $ClassesDirectory `
    "$PSScriptRoot/renderer/net/runelite/cache/HighDetailMapImageDumper.java" "$PSScriptRoot/RenderZoom3.java"
if ($LASTEXITCODE -ne 0) { throw 'Renderer compilation failed' }
& java -Xmx2g -cp ($ClassesDirectory + [IO.Path]::PathSeparator + $rendererClasspath) `
    RenderZoom3 $CacheDirectory $KeyFile $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Renderer failed' }
