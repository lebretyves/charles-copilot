import type { VentilatorFrame } from "../../types";
import { fmt } from "./format";

export function VentilatorDrager({ vent }: { vent?: VentilatorFrame }) {
  if (!vent) {
    return (
      <div className="vpd-block">
        <div className="vpd-hdr">
          <span className="vpd-brand">Drager</span>
          <span className="vpd-model">Perseus A500</span>
          <span className="vpd-offline">EN ATTENTE</span>
        </div>
      </div>
    );
  }

  const fr = vent.mv ? Math.round((vent.mv * 1000) / (vent.vt || 500)) : 14;

  return (
    <div className="vpd-block">
      <div className="vpd-hdr">
        <span className="vpd-brand">Drager</span>
        <span className="vpd-model">Perseus A500</span>
        <div className="vpd-modebox">
          <span className="vpd-modelbl">Mode</span>
          <span className="vpd-modeval">{vent.mode ?? "VCV"}</span>
        </div>
        {vent.ppeak > 28 && <span className="vpd-alarm-y">! Ppeak high</span>}
      </div>

      <div className="vpd-body">
        <div className="vpd-pgrid">
          {[
            { label: "Vt", value: fmt(vent.vt), unit: "mL", warn: false, sub: vent.vt_kg ? `${fmt(vent.vt_kg, 1)} mL/kg` : "" },
            { label: "FR", value: fmt(fr), unit: "/min", warn: false, sub: "" },
            { label: "Ppeak", value: fmt(vent.ppeak, 1), unit: "cmH2O", warn: vent.ppeak > 28, sub: "target 25" },
            { label: "Pplat", value: vent.pplat ? fmt(vent.pplat, 1) : "-", unit: "cmH2O", warn: false, sub: "" },
            { label: "PEEP", value: fmt(vent.peep, 1), unit: "cmH2O", warn: false, sub: `target ${fmt(vent.peep, 0)}` },
            { label: "VM", value: fmt(vent.mv, 1), unit: "L/min", warn: false, sub: "" },
            { label: "FiO2", value: fmt(vent.fio2), unit: "%", warn: false, sub: `target ${fmt(vent.fio2)}` },
            { label: "I:E", value: vent.ratio_ie ?? "1:2", unit: "", warn: false, sub: "" },
          ].map((param) => (
            <div key={param.label} className="vpdp">
              <div className="vpdp-lbl">{param.label}</div>
              <div className={`vpdp-meas ${param.warn ? "vpdp-meas--warn" : ""}`}>{param.value}<span className="vpdp-unit">{param.unit}</span></div>
              {param.sub && <div className="vpdp-set">{param.sub}</div>}
            </div>
          ))}
        </div>

        <div className="vpd-gas">
          <div className="vpd-gi"><div className="vpd-glbl">FiO2</div><div className="vpd-gval vpd-gval--yl">{fmt(vent.fio2)}%</div></div>
          <div className="vpd-gi"><div className="vpd-glbl">Ppeak</div><div className={`vpd-gval ${vent.ppeak > 28 ? "vpd-gval--rd" : "vpd-gval--gn"}`}>{fmt(vent.ppeak, 0)}</div></div>
          <div className="vpd-gi"><div className="vpd-glbl">Vt</div><div className="vpd-gval vpd-gval--cy">{fmt(vent.vt)} mL</div></div>
          <div className="vpd-gi"><div className="vpd-glbl">VM</div><div className="vpd-gval vpd-gval--gn">{fmt(vent.mv, 1)}</div></div>
          <div className="vpd-gi"><div className="vpd-glbl">PEEP</div><div className="vpd-gval vpd-gval--cy">{fmt(vent.peep, 0)}</div></div>
        </div>
      </div>
    </div>
  );
}

export function VentilatorGE({ vent }: { vent?: VentilatorFrame }) {
  if (!vent) {
    return (
      <div className="vga-block">
        <div className="vga-hdr">
          <span className="vga-brand">GE</span>
          <span className="vga-model">Aisys CS2</span>
          <span className="vga-offline">EN ATTENTE</span>
        </div>
      </div>
    );
  }

  const fr = vent.mv ? Math.round((vent.mv * 1000) / (vent.vt || 500)) : 14;

  return (
    <div className="vga-block">
      <div className="vga-hdr">
        <span className="vga-brand">GE</span>
        <span className="vga-model">Aisys CS2</span>
        <div className="vga-modebox">
          <span className="vga-modelbl">Mode</span>
          <span className="vga-modeval">{vent.mode ?? "VC-CMV"}</span>
        </div>
        {vent.ppeak > 28 && <span className="vga-alarm-y">! Ppeak high</span>}
      </div>

      <div className="vga-body">
        <div className="vga-pgrid">
          {[
            { label: "Vt", value: fmt(vent.vt), unit: "mL", warn: false },
            { label: "RR", value: fmt(fr), unit: "/min", warn: false },
            { label: "Ppeak", value: fmt(vent.ppeak, 1), unit: "cmH2O", warn: vent.ppeak > 28 },
            { label: "Pplat", value: vent.pplat ? fmt(vent.pplat, 1) : "-", unit: "cmH2O", warn: false },
            { label: "PEEP", value: fmt(vent.peep, 1), unit: "cmH2O", warn: false },
            { label: "VM", value: fmt(vent.mv, 1), unit: "L/min", warn: false },
            { label: "FiO2", value: fmt(vent.fio2), unit: "%", warn: false },
            { label: "I:E", value: vent.ratio_ie ?? "1:2", unit: "", warn: false },
          ].map((param) => (
            <div key={param.label} className="vgap">
              <div className="vgap-lbl">{param.label}</div>
              <div className={`vgap-meas ${param.warn ? "vgap-meas--warn" : ""}`}>{param.value}<span className="vgap-unit">{param.unit}</span></div>
            </div>
          ))}
        </div>

        <div className="vga-gas">
          <div className="vga-gi"><div className="vga-glbl">FiO2</div><div className="vga-gval vga-gval--yl">{fmt(vent.fio2)}%</div></div>
          <div className="vga-gi"><div className="vga-glbl">Ppeak</div><div className={`vga-gval ${vent.ppeak > 28 ? "vga-gval--rd" : "vga-gval--gn"}`}>{fmt(vent.ppeak, 0)}</div></div>
          <div className="vga-gi"><div className="vga-glbl">VM</div><div className="vga-gval vga-gval--cy">{fmt(vent.mv, 1)}</div></div>
        </div>
      </div>
    </div>
  );
}
