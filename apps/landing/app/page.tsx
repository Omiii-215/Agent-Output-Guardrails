import Nav from "./components/Nav";
import Hero from "./components/Hero";
import FinanceTicker from "./components/FinanceTicker";
import ProblemStatement from "./components/ProblemStatement";
import CapitalFlowVisualizer from "./components/CapitalFlowVisualizer";
import ThreeLayers from "./components/ThreeLayers";
import LivePolicySimulator from "./components/LivePolicySimulator";
import Pipeline from "./components/Pipeline";
import InjectionDemo from "./components/InjectionDemo";
import MakerChecker from "./components/MakerChecker";
import UnknownReconcile from "./components/UnknownReconcile";
import ModulesWall from "./components/ModulesWall";
import DatasetRun from "./components/DatasetRun";
import AuditTicker from "./components/AuditTicker";
import HonestySection from "./components/HonestySection";
import PersonaPicker from "./components/PersonaPicker";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <FinanceTicker />
        <ProblemStatement />
        <CapitalFlowVisualizer />
        <ThreeLayers />
        <LivePolicySimulator />
        <Pipeline />
        <InjectionDemo />
        <MakerChecker />
        <UnknownReconcile />
        <ModulesWall />
        <DatasetRun />
        <AuditTicker />
        <HonestySection />
        <PersonaPicker />
      </main>
      <Footer />
    </>
  );
}
