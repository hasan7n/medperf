var REDIRECT_BASE = "/benchmarks/ui/display/";

/* Which components each topology asks for. Mirrors TOPOLOGY_RULES on the
   server, so the form can only produce combinations the server accepts. */
var TOPOLOGIES = {
    byo_inference_script: {
        label: "Models bring their own inference",
        referenceModelInput: "reference-model-container",
        requires: ["evaluator-container"]
    },
    end_to_end_script: {
        label: "One script does everything",
        referenceModelInput: "reference-model-asset",
        requires: ["benchmark-script"]
    },
    inference_script: {
        label: "Your script infers, your container scores",
        referenceModelInput: "reference-model-asset",
        requires: ["benchmark-script", "evaluator-container"]
    }
};

function currentTopology() {
    var el = document.getElementById("topology");
    return el ? el.value : "";
}

function taskIsRunning() {
    var form = document.getElementById("benchmark-register-form");
    return Boolean(form && form.dataset.taskRunning === "true");
}

/* Enables the fields a topology uses and disables the rest. A disabled input is
   left out of the submitted FormData, so the server never receives a component
   the chosen topology does not use. While a task is running every field stays
   disabled, and only the show/hide part applies. */
function setTopologyFieldsState(topology) {
    var locked = taskIsRunning();
    document.querySelectorAll(".topology-field").forEach(function (field) {
        var applies = topology
            && (field.dataset.topologies || "").split(" ").indexOf(topology) !== -1;
        field.classList.toggle("hidden", !applies);
        field.querySelectorAll("input, select, textarea, button").forEach(function (el) {
            el.disabled = locked || !applies;
        });
    });
}

function applyTopology(topology) {
    var spec = TOPOLOGIES[topology];
    if (!spec) return;

    document.getElementById("topology").value = topology;
    var labelEl = document.getElementById("topology-label");
    if (labelEl) labelEl.textContent = spec.label;

    setTopologyFieldsState(topology);

    document.getElementById("topology-step").classList.add("hidden");
    document.getElementById("benchmark-register-form").classList.remove("hidden");
    checkBenchmarkFormValidity();
}

function showTopologyStep() {
    document.getElementById("benchmark-register-form").classList.add("hidden");
    document.getElementById("topology-step").classList.remove("hidden");
}

function requiredSelectionsFilled(topology) {
    var spec = TOPOLOGIES[topology];
    if (!spec) return false;

    var ids = spec.requires.concat([spec.referenceModelInput]);
    return ids.every(function (id) {
        var el = document.getElementById(id);
        return el && el.value && Number(el.value) > 0;
    });
}

function checkBenchmarkFormValidity() {
    var topology = currentTopology();
    var nameEl = document.getElementById("name");
    var descEl = document.getElementById("description");
    var urlEl = document.getElementById("reference-dataset-tarball-url");
    var dataPrepEl = document.getElementById("data-preparation-container");
    var skipTestsEl = document.getElementById("skip-tests");
    var noSkipTestsEl = document.getElementById("noskip-tests");

    var nameValue = nameEl ? nameEl.value.trim() : "";
    var descriptionValue = descEl ? descEl.value.trim() : "";
    var referenceDatasetTarballUrlValue = urlEl ? urlEl.value.trim() : "";
    var dataPreparationContainerValue = dataPrepEl && dataPrepEl.value ? Number(dataPrepEl.value) : 0;
    var skipTestsValue = skipTestsEl && skipTestsEl.checked ? true : false;
    var noskipTestsValue = noSkipTestsEl && noSkipTestsEl.checked ? true : false;

    var demoDatasetValid = noskipTestsValue
        ? referenceDatasetTarballUrlValue.length > 0
        : (!referenceDatasetTarballUrlValue.length && skipTestsValue);

    var isValid = Boolean(topology)
        && nameValue.length > 0
        && descriptionValue.length > 0
        && demoDatasetValid
        && dataPreparationContainerValue > 0
        && requiredSelectionsFilled(topology);

    var btn = document.getElementById("register-benchmark-btn");
    if (btn) btn.disabled = !isValid;
}

function init() {
    var form = document.getElementById("benchmark-register-form");
    if (form) {
        form.addEventListener("submit", submitActionForm);
        form.querySelectorAll("input, textarea, select").forEach(function (el) {
            el.addEventListener("keyup", checkBenchmarkFormValidity);
            el.addEventListener("change", checkBenchmarkFormValidity);
        });
    }

    document.querySelectorAll(".topology-option").forEach(function (el) {
        el.addEventListener("click", function () {
            applyTopology(el.dataset.topology);
        });
    });

    var changeBtn = document.getElementById("change-topology-btn");
    if (changeBtn) changeBtn.addEventListener("click", showTopologyStep);

    document.querySelectorAll("input[name='skip_compatibility_tests']").forEach(function (el) {
        el.addEventListener("change", function () {
            var skipTestsEl = document.getElementById("skip-tests");
            var demoContainer = document.getElementById("demo-dataset-input-container");
            var urlInput = document.getElementById("reference-dataset-tarball-url");
            if (skipTestsEl && skipTestsEl.checked) {
                if (demoContainer) demoContainer.style.display = "none";
                if (urlInput) urlInput.value = "";
            } else {
                if (demoContainer) demoContainer.style.display = "block";
            }
            checkBenchmarkFormValidity();
        });
    });

    /* A resumed task already carries a topology; otherwise the chooser stands. */
    var topology = currentTopology();
    if (topology) {
        applyTopology(topology);
    } else {
        setTopologyFieldsState("");
        checkBenchmarkFormValidity();
    }
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
