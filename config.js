// Shared MQTT contract (see TOPICS.md). Change the broker here for your own deployment.
window.SMARTFARM = {
  brokerUrl: "wss://broker.hivemq.com:8884/mqtt",
  root: "ecocomp/smartfarm",
  defaultFarm: "iringa-demo",
  twinUrl: "https://smart-farm-twin.vercel.app",  // update after deploying the twin
};
