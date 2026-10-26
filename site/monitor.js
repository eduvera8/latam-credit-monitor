// Crosshair + tooltip layer for the monitor's line charts.
//
// Each <svg class="chart"> carries its own data in data-series / data-dates, and
// its plot geometry is read off the .hitbox rect, so this file holds no copy of
// the margins defined in charts.py.

const SLOT_VAR = { 1: "--series-1", 2: "--series-2", 3: "--series-3" };

function fmt(value, decimals) {
  return value.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function monthLabel(iso) {
  const names = ["jan", "fev", "mar", "abr", "mai", "jun",
                 "jul", "ago", "set", "out", "nov", "dez"];
  const [year, month] = iso.split("-");
  return `${names[Number(month) - 1]}/${year}`;
}

function wire(svg) {
  const series = JSON.parse(svg.dataset.series);
  const dates = JSON.parse(svg.dataset.dates);
  const decimals = Number(svg.dataset.decimals || 2);
  const unit = svg.dataset.unit || "";

  const hitbox = svg.querySelector(".hitbox");
  const crosshair = svg.querySelector(".crosshair");
  const dotGroup = svg.querySelector(".hoverdots");
  if (!hitbox || !crosshair || !dotGroup) return;

  const plotX = Number(hitbox.getAttribute("x"));
  const plotY = Number(hitbox.getAttribute("y"));
  const plotW = Number(hitbox.getAttribute("width"));
  const plotH = Number(hitbox.getAttribute("height"));

  // The chart publishes its y-domain, so the hover dots use exactly the scale
  // charts.py drew with - no reverse-engineering of tick labels.
  const yLo = Number(svg.dataset.ylo);
  const yHi = Number(svg.dataset.yhi);
  const toY = (v) => plotY + plotH - (plotH * (v - yLo)) / (yHi - yLo);

  const wrap = svg.closest(".chart-wrap");
  const scroller = svg.closest(".chart-scroll");
  const tooltip = wrap.querySelector(".tooltip");

  const toLocal = (event) => {
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  };

  function show(event) {
    const local = toLocal(event);
    const frac = (local.x - plotX) / plotW;
    const i = Math.max(0, Math.min(dates.length - 1, Math.round(frac * (dates.length - 1))));
    const x = plotX + (plotW * i) / (dates.length - 1);

    crosshair.setAttribute("x1", x);
    crosshair.setAttribute("x2", x);
    crosshair.removeAttribute("hidden");

    dotGroup.replaceChildren();
    const rows = [];
    for (const s of series) {
      const v = s.values[i];
      if (v === null || v === undefined) continue;
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("class", "hoverdot");
      dot.setAttribute("cx", x);
      dot.setAttribute("cy", toY(v));
      dot.setAttribute("r", 4);
      dot.style.fill = `var(${SLOT_VAR[s.slot]})`;
      dotGroup.appendChild(dot);
      rows.push(
        `<div class="tt-row"><span class="tt-swatch" style="background:var(${SLOT_VAR[s.slot]})"></span>` +
          `<span class="tt-label">${s.label}</span>` +
          `<span class="tt-val">${fmt(v, decimals)}</span></div>`
      );
    }
    if (!rows.length) return;

    tooltip.innerHTML =
      `<p class="tt-date">${monthLabel(dates[i])}${unit ? ` · ${unit}` : ""}</p>` + rows.join("");
    tooltip.dataset.open = "1";

    // Place the tooltip beside the crosshair, flipping before it leaves the card.
    const box = svg.getBoundingClientRect();
    const wrapBox = wrap.getBoundingClientRect();
    const pxPerUnit = box.width / svg.viewBox.baseVal.width;
    // box.left already includes the scroller's offset, so measure against the
    // wrap (which does not scroll) and clamp inside it.
    let left = box.left - wrapBox.left + x * pxPerUnit + 14;
    if (left + tooltip.offsetWidth > wrapBox.width) {
      left = box.left - wrapBox.left + x * pxPerUnit - tooltip.offsetWidth - 14;
    }
    tooltip.style.left = `${Math.max(0, left)}px`;
    tooltip.style.top = `${plotY * pxPerUnit}px`;
  }

  function hide() {
    crosshair.setAttribute("hidden", "");
    dotGroup.replaceChildren();
    tooltip.dataset.open = "0";
  }

  hitbox.addEventListener("pointermove", show);
  hitbox.addEventListener("pointerdown", show);
  hitbox.addEventListener("pointerleave", hide);
}

function wireBars(svg) {
  const wrap = svg.closest(".chart-wrap");
  const tooltip = wrap.querySelector(".tooltip");
  const decimals = Number(svg.dataset.decimals || 1);
  const unit = svg.dataset.unit || "";

  svg.querySelectorAll("path.bar").forEach((bar) => {
    bar.addEventListener("pointerenter", () => {
      tooltip.innerHTML =
        `<p class="tt-date">${bar.dataset.label}</p>` +
        `<div class="tt-row"><span class="tt-swatch" style="background:var(--series-1)"></span>` +
        `<span class="tt-label">Var. 12m</span>` +
        `<span class="tt-val">${fmt(Number(bar.dataset.value), decimals)}${unit ? ` ${unit}` : ""}</span></div>`;
      tooltip.dataset.open = "1";

      const box = bar.getBoundingClientRect();
      const wrapBox = wrap.getBoundingClientRect();
      let left = box.right - wrapBox.left + 12;
      if (left + tooltip.offsetWidth > wrapBox.width) {
        left = box.left - wrapBox.left - tooltip.offsetWidth - 12;
      }
      tooltip.style.left = `${Math.max(0, left)}px`;
      tooltip.style.top = `${box.top - wrapBox.top - 6}px`;
    });
    bar.addEventListener("pointerleave", () => {
      tooltip.dataset.open = "0";
    });
  });
}

document.querySelectorAll("svg.chart").forEach((svg) => {
  if (svg.classList.contains("chart-bars")) wireBars(svg);
  else wire(svg);
});
