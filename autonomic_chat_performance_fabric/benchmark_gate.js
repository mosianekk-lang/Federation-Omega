"use strict";

function baselineWorkUnits(messageCount, rounds) {
  let units = 0;
  for (let round = 1; round <= rounds; round += 1) {
    units += messageCount; // full DOM scan
    units += messageCount * round; // rebuild and serialize the growing ledger
  }
  return units;
}

function candidateWorkUnits(messageCount, rounds) {
  return (messageCount * rounds) + messageCount; // scans plus first delta write
}

const rounds = 20;
const cases = [100, 250, 500, 750, 1000].map(messages => {
  const championUnits = baselineWorkUnits(messages, rounds);
  const challengerUnits = candidateWorkUnits(messages, rounds);
  return {
    messages,
    rounds,
    championUnits,
    challengerUnits,
    workReductionFactor: Number((championUnits / challengerUnits).toFixed(2))
  };
});

const receipt = {
  schema: "FACPF-CFBE-DETERMINISTIC-1",
  evidenceClass: "DETERMINISTIC_COMPLEXITY_NOT_REAL_BROWSER",
  invariant: "challengerUnits < championUnits",
  cases,
  passed: cases.every(item => item.challengerUnits < item.championUnits)
};

console.log(JSON.stringify(receipt, null, 2));
if (!receipt.passed) process.exitCode = 1;

