#!/usr/bin/env node

const { execSync } = require("child_process");

const SEVERITY_ORDER = ["info", "low", "moderate", "high", "critical"];
const MIN_SEVERITY = process.env.AUDIT_MIN_SEVERITY || "moderate";
const minIndex = SEVERITY_ORDER.indexOf(MIN_SEVERITY);

function runAudit() {
  try {
    const output = execSync("npm audit --json", {
      cwd: __dirname + "/..",
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "pipe"],
    });
    const result = JSON.parse(output);
    printSummary(result);
    process.exit(0);
  } catch (error) {
    if (error.stdout) {
      try {
        const result = JSON.parse(error.stdout);
        printSummary(result);
        const hasCritical = hasSeverity(result, minIndex);
        process.exit(hasCritical ? 1 : 0);
      } catch {
        console.error("Failed to parse npm audit output:", error.stdout);
        process.exit(1);
      }
    } else {
      console.error("npm audit failed:", error.message);
      process.exit(1);
    }
  }
}

function hasSeverity(result, minIdx) {
  const advisories = result.advisories || {};
  for (const key of Object.keys(advisories)) {
    const adv = advisories[key];
    const idx = SEVERITY_ORDER.indexOf(adv.severity);
    if (idx >= minIdx) return true;
  }
  return false;
}

function printSummary(result) {
  const metadata = result.metadata || {};
  const vulns = metadata.vulnerabilities || {};
  console.log("\n=== Security Audit Summary ===");
  console.log(`Info:      ${vulns.info || 0}`);
  console.log(`Low:       ${vulns.low || 0}`);
  console.log(`Moderate:  ${vulns.moderate || 0}`);
  console.log(`High:      ${vulns.high || 0}`);
  console.log(`Critical:  ${vulns.critical || 0}`);

  const advisories = result.advisories || {};
  const filtered = Object.keys(advisories)
    .map((k) => advisories[k])
    .filter((adv) => SEVERITY_ORDER.indexOf(adv.severity) >= minIndex);

  if (filtered.length > 0) {
    console.log(`\n=== Vulnerabilities at or above ${MIN_SEVERITY} ===`);
    filtered.forEach((adv) => {
      console.log(`- [${adv.severity.toUpperCase()}] ${adv.module_name}: ${adv.title}`);
      console.log(`  Range: ${adv.vulnerable_versions}`);
      console.log(`  Patched: ${adv.patched_versions || "No patch available"}`);
      console.log(`  More info: ${adv.url}`);
    });
  } else {
    console.log(`\nNo vulnerabilities at or above ${MIN_SEVERITY} severity found.`);
  }
}

runAudit();
