param(
    [Parameter(Mandatory=$true)][string]$ImagePath,
    [string]$Target = '',
    [string]$Language = 'zh-Hans-CN'
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]

function Await-Operation($AsyncOperation, [type]$ResultType) {
    $methods = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethodDefinition -and
            $_.GetParameters().Count -eq 1
        }
    $method = $methods[0].MakeGenericMethod($ResultType)
    $task = $method.Invoke($null, @($AsyncOperation))
    return $task.GetAwaiter().GetResult()
}

function Normalize-Text([string]$Text) {
    return ($Text -replace '\s+', '' -replace '[^\p{IsCJKUnifiedIdeographs}A-Za-z0-9]', '')
}

$fullPath = [System.IO.Path]::GetFullPath($ImagePath)
$file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)) ([Windows.Storage.StorageFile])
$stream = Await-Operation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$lang = [Windows.Globalization.Language]::new($Language)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {
    throw "Cannot create OCR engine for $Language."
}
$result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$lines = @()
foreach ($line in $result.Lines) {
    $minX = [double]::PositiveInfinity
    $minY = [double]::PositiveInfinity
    $maxX = 0.0
    $maxY = 0.0
    $words = @()
    foreach ($word in $line.Words) {
        $r = $word.BoundingRect
        $minX = [Math]::Min($minX, [double]$r.X)
        $minY = [Math]::Min($minY, [double]$r.Y)
        $maxX = [Math]::Max($maxX, [double]$r.X + [double]$r.Width)
        $maxY = [Math]::Max($maxY, [double]$r.Y + [double]$r.Height)
        $words += [ordered]@{
            Text = $word.Text
            X = [double]$r.X
            Y = [double]$r.Y
            Width = [double]$r.Width
            Height = [double]$r.Height
        }
    }
    if ($words.Count -eq 0) {
        continue
    }
    $lines += [ordered]@{
        Text = $line.Text
        Normalized = Normalize-Text $line.Text
        X = $minX
        Y = $minY
        Width = ($maxX - $minX)
        Height = ($maxY - $minY)
        Words = $words
    }
}

$hits = @()
$targetNorm = Normalize-Text $Target
if ($targetNorm.Length -gt 0) {
    foreach ($line in $lines) {
        if ($line.Normalized.Contains($targetNorm)) {
            $hits += $line
        }
    }
}

[ordered]@{
    Image = $fullPath
    Target = $Target
    Text = (($lines | ForEach-Object { $_.Text }) -join "`n")
    Lines = $lines
    Hits = $hits
} | ConvertTo-Json -Depth 8 -Compress
