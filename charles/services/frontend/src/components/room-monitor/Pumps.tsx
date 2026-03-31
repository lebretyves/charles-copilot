import type { AIVOCFrame } from "../../types";
import { fmt } from "./format";

function PumpChannel({ drug, color, labelColor }: { drug: AIVOCFrame; color: string; labelColor: string }) {
  const isHypnotic = drug.target_type === "effect" || drug.drug.toLowerCase().includes("propo");
  const unit = isHypnotic ? "ug/mL" : "ng/mL";
  const ratio = Math.min(100, drug.target > 0 ? (drug.predicted_effect / drug.target) * 100 : 0);

  return (
    <div className="psb-chan">
      <div className="psb-chan-top">
        <div className="psb-colorband" style={{ background: color }}>
          <span className="psb-colorband-text">{drug.drug.substring(0, 4).toUpperCase()}</span>
        </div>
        <div className="psb-chaninfo">
          <div className="psb-drugname" style={{ color: labelColor }}>{drug.drug.toUpperCase()}</div>
          <div className="psb-drugconc">{drug.model} · {drug.target_type}</div>
          <div className="psb-cecp">
            <span className="psb-ce-val" style={{ color }}>{fmt(drug.predicted_effect, 2)}</span>
            <span className="psb-ce-lbl">{unit} Ce</span>
          </div>
          <div className="psb-cp-row">Cp {fmt(drug.predicted_plasma, 2)} {unit} - {fmt(drug.infusion_rate, 1)} mL/h</div>
        </div>
        <div className="psb-chanright">
          <div className="psb-tgt-box" style={{ borderColor: color }}>
            <div className="psb-tgt-val" style={{ color }}>{fmt(drug.target, 1)}</div>
            <div className="psb-tgt-unit" style={{ color }}>{unit}</div>
          </div>
          <div className="psb-debit">{fmt(drug.infusion_rate, 1)}mL/h</div>
        </div>
      </div>
      <div className="psb-progbar">
        <div className="psb-pbar" style={{ width: `${ratio}%`, background: color }}></div>
      </div>
    </div>
  );
}

function FresPumpChannel({ drug, color, textColor }: { drug: AIVOCFrame; color: string; textColor: string }) {
  const isHypnotic = drug.target_type === "effect" || drug.drug.toLowerCase().includes("propo");
  const unit = isHypnotic ? "ug/mL" : "ng/mL";
  const ratio = Math.min(100, drug.target > 0 ? (drug.predicted_effect / drug.target) * 100 : 0);

  return (
    <div className="psf-chan">
      <div style={{ display: "flex", alignItems: "stretch", flex: 1, minHeight: 0 }}>
        <div className="psf-colorband" style={{ background: color }}>
          <span className="psf-colorband-text">{drug.drug.substring(0, 4).toUpperCase()}</span>
        </div>
        <div className="psf-chaninfo">
          <div className="psf-drugname" style={{ color: textColor }}>{drug.drug.toUpperCase()}</div>
          <div className="psf-conc">{drug.model} · {drug.target_type}</div>
          <div className="psf-cerow">
            <span className="psf-ce-val" style={{ color: textColor }}>{fmt(drug.predicted_effect, 2)}</span>
            <span className="psf-ce-lbl">{unit} Ce</span>
          </div>
          <div className="psf-cp-row">Cp {fmt(drug.predicted_plasma, 2)} - {fmt(drug.infusion_rate, 1)} mL/h</div>
        </div>
        <div className="psf-chanright">
          <div className="psf-tgt-box" style={{ borderColor: color }}>
            <div className="psf-tgt-val" style={{ color: textColor }}>{fmt(drug.target, 1)}</div>
            <div className="psf-tgt-unit" style={{ color: textColor }}>{unit}</div>
          </div>
          <div className="psf-debit">{fmt(drug.infusion_rate, 1)}mL/h</div>
        </div>
      </div>
      <div className="psb-progbar" style={{ background: "#1a1a18" }}>
        <div className="psb-pbar" style={{ width: `${ratio}%`, background: color }}></div>
      </div>
    </div>
  );
}

export function PumpBraun({ hyp, opi }: { hyp?: AIVOCFrame; opi?: AIVOCFrame }) {
  return (
    <div className="psb-block">
      <div className="psb-statusbar">
        <span className="psb-sb-dot"></span>
        <span className="psb-sb-txt">SPACE / OK</span>
        {hyp && <span className="psb-sb-alm">{hyp.drug.toUpperCase()} actif</span>}
      </div>
      <div className="psb-logobnd">
        <span className="psb-logo">B|BRAUN</span>
        <span className="psb-logo-sub">Space</span>
        <span className="psb-tcimode">TCI actif</span>
      </div>
      <div className="psb-channels">
        {hyp ? <PumpChannel drug={hyp} color="#e8a000" labelColor="#ffc84c" /> : <div className="psb-chan psb-chan--empty"><span>Hypnotique - aucune TCI</span></div>}
        {opi ? <PumpChannel drug={opi} color="#9030e0" labelColor="#c080f0" /> : <div className="psb-chan psb-chan--empty"><span>Opioide - aucune TCI</span></div>}
        <div className="psb-chan psb-chan--empty" style={{ background: "#1a0808" }}>
          <div className="psb-chan-top">
            <div className="psb-colorband" style={{ background: "#b00020" }}>
              <span className="psb-colorband-text">VAS</span>
            </div>
            <div className="psb-chaninfo">
              <div className="psb-drugname" style={{ color: "#f04060" }}>VASOPRESSEUR</div>
              <div className="psb-drugconc" style={{ color: "#805060" }}>Non actif</div>
            </div>
          </div>
        </div>
      </div>
      <div className="psb-btnbar">
        <div className="psb-btn psb-btn--red">STOP</div>
        <div className="psb-btn psb-btn--blue">MODIFIER</div>
        <div className="psb-btn">BOLUS</div>
        <div className="psb-btn">HISTORIQ.</div>
      </div>
    </div>
  );
}

export function PumpFresenius({ hyp, opi }: { hyp?: AIVOCFrame; opi?: AIVOCFrame }) {
  return (
    <div className="psf-block">
      <div className="psf-statusbar">
        <span className="psf-sb-dot"></span>
        <span className="psf-sb-txt">AGILIA ORCHESTRA / OK</span>
        {hyp && <span className="psb-sb-alm">{hyp.drug.toUpperCase()} actif</span>}
      </div>
      <div className="psf-logobnd">
        <span className="psf-logo">Fresenius</span>
        <span className="psf-model">Agilia SP TCI</span>
        <span className="psf-mode-tag">TCI</span>
      </div>
      <div className="psf-channels">
        {hyp ? <FresPumpChannel drug={hyp} color="#d08800" textColor="#f0a800" /> : <div className="psf-chan psf-chan--empty"><span>Hypnotique - aucune TCI</span></div>}
        {opi ? <FresPumpChannel drug={opi} color="#7820c0" textColor="#c080f0" /> : <div className="psf-chan psf-chan--empty"><span>Opioide - aucune TCI</span></div>}
        <div className="psf-chan psf-chan--empty" style={{ background: "#1a0006" }}>
          <div style={{ display: "flex", alignItems: "stretch", flex: 1, minHeight: 0 }}>
            <div className="psf-colorband" style={{ background: "#c00030" }}>
              <span className="psf-colorband-text">NOR</span>
            </div>
            <div className="psf-chaninfo">
              <div className="psf-drugname" style={{ color: "#f04060" }}>NORADRENALINE</div>
              <div className="psf-conc" style={{ color: "#502030" }}>Non actif</div>
            </div>
          </div>
        </div>
      </div>
      <div className="psf-btnbar">
        <div className="psf-btn psf-btn--stop">STOP</div>
        <div className="psf-btn">PAUSE</div>
        <div className="psf-btn">MODIF.</div>
        <div className="psf-btn">BOLUS</div>
        <div className="psf-btn">HISTOR.</div>
      </div>
    </div>
  );
}
