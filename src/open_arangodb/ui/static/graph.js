// Cytoscape wiring for the graph page.
(async function () {
  const mount = document.getElementById("cy");
  if (!mount || typeof cytoscape === "undefined") return;

  const res = await fetch("/ui/graph.json");
  const data = await res.json();

  const elements = [];
  for (const n of data.nodes || []) {
    elements.push({ data: { id: n.id, label: n.label, collection: n.collection } });
  }
  for (const e of data.edges || []) {
    if (!e.source || !e.target) continue;
    elements.push({ data: { id: e.id, source: e.source, target: e.target, kind: e.kind } });
  }

  const cy = cytoscape({
    container: mount,
    elements,
    layout: { name: "cose", animate: true, animationDuration: 600, padding: 24, idealEdgeLength: 120 },
    style: [
      {
        selector: "node",
        style: {
          "background-color": "#55E2CF",
          "border-color": "#97F5E6",
          "border-width": 1,
          "width": 36, "height": 36,
          "label": "data(label)",
          "color": "#F1ECDC",
          "font-family": "'Archivo', sans-serif",
          "font-size": 11,
          "font-weight": 500,
          "text-valign": "bottom", "text-margin-y": 8,
          "text-background-color": "rgba(6,15,30,0.7)",
          "text-background-opacity": 1,
          "text-background-padding": "3px",
          "text-background-shape": "roundrectangle",
          "text-border-opacity": 0,
          "overlay-opacity": 0,
          "transition-property": "background-color, border-color, width, height",
          "transition-duration": 160
        }
      },
      { selector: "node:selected", style: { "background-color": "#FFA24B", "border-color": "#FFC38A", "width": 44, "height": 44 } },
      {
        selector: "edge",
        style: {
          "width": 1.4,
          "line-color": "#FFA24B",
          "opacity": 0.75,
          "curve-style": "bezier",
          "target-arrow-color": "#FFA24B",
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.9,
          "label": "data(kind)",
          "font-family": "'JetBrains Mono', monospace",
          "font-size": 9,
          "color": "rgba(241,236,220,0.5)",
          "text-rotation": "autorotate",
          "text-margin-y": -6,
        }
      }
    ]
  });

  // readout updates
  const readout = document.getElementById("graph-readout");
  const update = () => {
    if (!readout) return;
    readout.textContent = `nodes ${cy.nodes().length}  ·  edges ${cy.edges().length}`;
  };
  update();
  cy.on("select", "node", (evt) => {
    if (readout) readout.textContent = `selected · ${evt.target.data("label")}`;
  });
})();
