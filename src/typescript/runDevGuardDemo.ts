import { demoScenarios, pretty } from "./bbsDevGuardMvp";

function main(): void {
  for (const [name, payload] of demoScenarios()) {
    console.log(`== ${name} ==`);
    console.log(pretty(payload));
  }
}

main();
