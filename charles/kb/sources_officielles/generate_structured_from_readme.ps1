param(
    [switch]$SourcesOnly
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot

function Slugify-Text {
    param([string]$Text)
    $slug = $Text.ToLowerInvariant()
    $slug = $slug -replace "[^a-z0-9]+", "_"
    $slug = $slug.Trim("_")
    if (-not $slug) { $slug = "item" }
    return $slug
}

function Write-YamlFile {
    param(
        [string]$Path,
        [string[]]$Lines
    )
    Set-Content -Path $Path -Value ($Lines -join "`r`n") -Encoding UTF8
}

function Parse-ReadmeSections {
    param([string[]]$Lines)
    $sections = [ordered]@{}
    $current = "__preamble__"
    $sections[$current] = @()
    foreach ($line in $Lines) {
        if ($line -match '^##\s+(.+)$') {
            $current = $Matches[1].Trim()
            $sections[$current] = @()
            continue
        }
        $sections[$current] += $line
    }
    return $sections
}

function Get-Bullets {
    param([object[]]$Lines)
    $bullets = @()
    foreach ($line in $Lines) {
        if ($line -match '^\-\s+(.+)$') {
            $bullets += $Matches[1].Trim()
        }
    }
    return $bullets
}

function Infer-Org {
    param([string]$Bullet)
    if ($Bullet -like "SFAR*") { return "SFAR" }
    if ($Bullet -like "MAPAR*") { return "MAPAR" }
    if ($Bullet -like "SOFIA*") { return "SOFIA" }
    return "UNKNOWN"
}

function Parse-SourceBullet {
    param([string]$Bullet)
    $org = Infer-Org $Bullet
    $title = $Bullet
    $url = ""
    if ($Bullet -match '^(.*?):\s+(https?://.+)$') {
        $title = $Matches[1].Trim()
        $url = $Matches[2].Trim()
    }
    return @{
        org = $org
        title = $title
        url = $url
        source_id = (Slugify-Text $title)
    }
}

$directories = Get-ChildItem -Path $root -Directory -Recurse |
    Where-Object {
        ($_.FullName -like "*\terrains\*") -or ($_.FullName -like "*\complications\*")
    } |
    Where-Object {
        Test-Path (Join-Path $_.FullName "README.md")
    } |
    Where-Object {
        $_.Name -notin @("terrains", "complications")
    }

foreach ($directory in $directories) {
    $readmePath = Join-Path $directory.FullName "README.md"
    $lines = Get-Content $readmePath
    $sections = Parse-ReadmeSections $lines

    $idLine = $lines | Where-Object { $_ -match '^\-\s+`id`:\s+`(.+)`$' } | Select-Object -First 1
    $id = if ($idLine -match '^\-\s+`id`:\s+`(.+)`$') { $Matches[1] } else { $directory.Name }
    $confidenceLine = $lines | Where-Object { $_ -match '^\-\s+`confiance_algo`:\s+`(.+)`$' } | Select-Object -First 1
    $confidence = if ($confidenceLine -match '^\-\s+`confiance_algo`:\s+`(.+)`$') { $Matches[1] } else { "a_confirmer" }
    $topicType = if ($directory.FullName -like "*\terrains\*") { "terrain" } else { "complication" }

    $sourceBullets = Get-Bullets $sections["Sources"]
    $sources = @($sourceBullets | ForEach-Object { Parse-SourceBullet $_ })

    $factSectionNames = @("Ce que les sources apportent", "Ce que la base source permet deja")
    $factBullets = @()
    foreach ($sectionName in $factSectionNames) {
        if ($sections.Contains($sectionName)) {
            $factBullets += Get-Bullets $sections[$sectionName]
        }
    }

    $inferenceSectionNames = @("Exploitation algo possible", "Signaux utiles pour algo", "Regles candidates", "Combinaisons pertinentes", "Pistes KB")
    $inferenceBullets = @()
    foreach ($sectionName in $inferenceSectionNames) {
        if ($sections.Contains($sectionName)) {
            $sectionBullets = Get-Bullets $sections[$sectionName]
            foreach ($bullet in $sectionBullets) {
                $inferenceBullets += @{
                    section = $sectionName
                    bullet = $bullet
                }
            }
        }
    }

    $sourceLines = @(
        "topic_id: $id",
        "topic_type: $topicType",
        "date_consultation: 2026-04-01",
        "sources:"
    )
    foreach ($source in $sources) {
        $sourceLevel = if ($source.org -eq "SFAR") {
            "normatif"
        } elseif ($source.org -eq "MAPAR") {
            "pratique"
        } elseif ($source.org -eq "SOFIA") {
            "pedagogique"
        } else {
            "a_valider"
        }
        $supportType = if ($source.url -like "*.pdf") { "pdf" } else { "webpage" }
        $sourceLines += @(
            "  - source_id: $($source.source_id)",
            "    organisme: $($source.org)",
            "    niveau_source: $sourceLevel",
            "    title: ""$($source.title)""",
            "    url: ""$($source.url)""",
            "    support_type: $supportType",
            "    date_consultation: 2026-04-01"
        )
    }
    Write-YamlFile -Path (Join-Path $directory.FullName "sources.yaml") -Lines $sourceLines

    if ($SourcesOnly) {
        continue
    }

    $factLines = @(
        "topic_id: $id",
        "faits:"
    )
    $factIndex = 1
    foreach ($fact in $factBullets) {
        $sourceRef = if ($sources.Count -gt 0) { $sources[0].source_id } else { "a_renseigner" }
        $factLines += @(
            "  - fact_id: fact_$('{0:d2}' -f $factIndex)",
            "    statut: direct_source",
            "    force_source: " + ($(if ($confidence -eq "forte") { "normative_or_supported" } else { "supported_but_to_review" })),
            "    fact_type: structured_summary",
            "    statement: ""$fact""",
            "    source_ref: $sourceRef"
        )
        $factIndex += 1
    }
    if ($factBullets.Count -eq 0) {
        $factLines += @(
            "  - fact_id: fact_01",
            "    statut: direct_source",
            "    force_source: supported_but_to_review",
            "    fact_type: placeholder",
            "    statement: ""Aucune extraction factuelle directe n'a encore ete detaillee dans le README de ce dossier.""",
            "    source_ref: " + ($(if ($sources.Count -gt 0) { $sources[0].source_id } else { "a_renseigner" }))
        )
    }
    Write-YamlFile -Path (Join-Path $directory.FullName "faits_source.yaml") -Lines $factLines

    $inferenceLines = @(
        "topic_id: $id",
        "inferences:"
    )
    $inferenceIndex = 1
    foreach ($entry in $inferenceBullets) {
        $kind = switch ($entry.section) {
            "Exploitation algo possible" { "algorithm_design" }
            "Signaux utiles pour algo" { "monitoring_target" }
            "Regles candidates" { "rule_candidate" }
            "Combinaisons pertinentes" { "combination_candidate" }
            "Pistes KB" { "kb_extension" }
            default { "design_proposal" }
        }
        $derivedFrom = if ($factBullets.Count -gt 0) { "fact_01" } else { "a_renseigner" }
        $inferenceLines += @(
            "  - inference_id: inf_$('{0:d2}' -f $inferenceIndex)",
            "    status: design_proposal",
            "    kind: $kind",
            "    proposal: ""$($entry.bullet)""",
            "    derived_from:",
            "      - $derivedFrom"
        )
        $inferenceIndex += 1
    }
    Write-YamlFile -Path (Join-Path $directory.FullName "inferences_algo.yaml") -Lines $inferenceLines

    $validationStatus = switch ($confidence) {
        "forte" { "a_valider" }
        "mixte" { "a_completer" }
        default { "a_completer" }
    }
    $validationLines = @(
        "topic_id: $id",
        "overall_status: $validationStatus",
        "last_reviewed: 2026-04-01",
        "direct_source_extraction_level: partiel",
        "open_points:",
        "  - ""Verifier les valeurs numeriques exactes directement dans les documents sources avant de les transformer en regles strictes.""",
        "  - ""Completer les references ligne a ligne si ce dossier doit servir de base a un score pondere formel."""
    )
    Write-YamlFile -Path (Join-Path $directory.FullName "validation.yaml") -Lines $validationLines
}
