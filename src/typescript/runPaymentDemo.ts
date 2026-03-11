import { demoScenarios, pretty } from "./bbsPaymentMvp";

function main(): void {
  for (const [name, payload] of demoScenarios()) {
    console.log(`== ${name} ==`);
    console.log(pretty(payload));
  }
}

main();
