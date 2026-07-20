/**
 * Keeps Dash dashboard theme in sync with MedPerf WebUI (localStorage medperf-dark).
 */
(function () {
    var FONT = "Instrument Sans, ui-sans-serif, system-ui, sans-serif";
    var INK = "#11141f";
    var SURFACE = "#f7f8fa";
    var CARD_DARK = "#1f2433";
    var TEXT_DARK = "#e5e7eb";
    var TEXT_DARK_BRIGHT = "#ffffff";

    function medperfDashIsDark() {
        try {
            var v = localStorage.getItem("medperf-dark");
            return (
                v === "1" ||
                (v === null &&
                    window.matchMedia &&
                    window.matchMedia("(prefers-color-scheme: dark)").matches)
            );
        } catch (e) {
            return false;
        }
    }

    function medperfPlotlyLayoutPatch(gd, dark) {
        var text = dark ? TEXT_DARK : INK;
        var centerText = dark ? TEXT_DARK_BRIGHT : INK;
        var plotBg = dark ? CARD_DARK : SURFACE;
        var grid = dark ? "#3d455a" : "#d8dce6";
        var axis = dark ? "#6b7280" : "#9b9fad";
        var zero = dark ? "#4b5563" : "#d8dce6";
        var legendBg = dark ? "rgba(24,28,40,0.95)" : "rgba(247,248,250,0.95)";
        var legendBorder = dark ? "#3d455a" : "#ebeef4";

        var patch = {
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: plotBg,
            "font.color": text,
            "title.font.color": centerText,
            "legend.font.color": text,
            "legend.bgcolor": legendBg,
            "legend.bordercolor": legendBorder,
        };

        var layout = gd.layout || {};
        var key;
        for (key in layout) {
            if (/^xaxis\d*$/.test(key) || /^yaxis\d*$/.test(key)) {
                patch[key + ".tickfont.color"] = text;
                patch[key + ".title.font.color"] = text;
                patch[key + ".gridcolor"] = grid;
                patch[key + ".linecolor"] = axis;
                patch[key + ".zerolinecolor"] = zero;
            }
        }

        if (layout.annotations && layout.annotations.length) {
            var i;
            for (i = 0; i < layout.annotations.length; i++) {
                patch["annotations[" + i + "].font.color"] = centerText;
            }
        }

        return patch;
    }

    function medperfPlotlyRelayout() {
        if (typeof window.Plotly === "undefined") return;
        var dark = document.documentElement.classList.contains("dark");
        var text = dark ? TEXT_DARK : INK;
        var sliceLabel = dark ? TEXT_DARK_BRIGHT : INK;
        var plots = document.querySelectorAll(".js-plotly-plot");
        var i;
        var gd;

        for (i = 0; i < plots.length; i++) {
            gd = plots[i];
            try {
                window.Plotly.relayout(gd, medperfPlotlyLayoutPatch(gd, dark));
                window.Plotly.restyle(gd, {
                    "textfont.color": sliceLabel,
                    "insidetextfont.color": sliceLabel,
                    "outsidetextfont.color": sliceLabel,
                });
            } catch (e) {
                /* ignore per-figure errors */
            }
        }
    }

    function medperfDashApplyTheme(dark) {
        document.documentElement.classList.toggle("dark", !!dark);
        medperfPlotlyRelayout();
        setTimeout(medperfPlotlyRelayout, 200);
        setTimeout(medperfPlotlyRelayout, 800);
        setTimeout(medperfPlotlyRelayout, 2000);
    }

    window.addEventListener("message", function (ev) {
        if (!ev.data || ev.data.type !== "medperf-theme") return;
        medperfDashApplyTheme(!!ev.data.dark);
    });

    window.addEventListener("storage", function (ev) {
        if (ev.key !== "medperf-dark") return;
        medperfDashApplyTheme(ev.newValue === "1");
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            medperfDashApplyTheme(medperfDashIsDark());
        });
    } else {
        medperfDashApplyTheme(medperfDashIsDark());
    }
})();
