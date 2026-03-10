// Vérifiez si d'autres gestionnaires sont attachés
setTimeout(function () {
    var elem = document.getElementById('save_collection_btn');
    var events = $._data(elem, 'events');
    console.log('Événements attachés:', events);
}, 2000);

// Remove active sample from localStorage on window load
window.onload = function () {
    localStorage.removeItem("activeSample");
};

// Check if there is an active sample and enable/disable the collect button accordingly
function checkAndDisableCollectButton() {
    const isActiveSample = localStorage.getItem("activeSample") !== null;
    $("#collect").prop("disabled", !isActiveSample);
}

// Render the sample elements based on the data fetched
function renderElement(data) {
    const $renderedSample = $("#rendered_sample").empty();

    if (Array.isArray(data) && data.length > 0) {
        const htmlContent = data
            .map(
                (item) =>
                    `<div class="sample_item" id="sample-${item.id}">${item.sample_type_id}<br></div>`
            )
            .join("");
        const $wrappedHtml = `<div class="items">
      ${htmlContent}
      </div>`;
        $renderedSample.html($wrappedHtml);
        bindSampleItemClick(data);
    } else {
        $renderedSample.html(renderEmptyData());
    }
}

function renderEmptyData() {
    return `
      <div class="content">
        <h4>Aucune donnée trouvée</h4>
        <span class="material-symbols-outlined">hourglass_empty</span>
      </div>`;
}

// Bind click event to each sample item to display its details
function bindSampleItemClick(data) {
    $(".sample_item").click(function () {
        const itemId = $(this).attr("id").split("-")[1];
        const selectedItem = data.find((item) => item.id == itemId);
        displayItemDetails(selectedItem);
    });
}

// Display details of the selected item
function displayItemDetails(item) {
    localStorage.setItem("activeSample", JSON.stringify(item));

    checkAndDisableCollectButton();

    $("#sample_details").empty();
    $(".sample_item").removeClass("active");
    $(`#sample-${item.id}`).addClass("active");

    const detailsHtml = buildDetailsHtml(item);
    $("#sample_details").html(detailsHtml);

    // Bind quantity update buttons
    bindQuantityButtons();
    $(".lot-input").each((index, input) => {
        let timerLot = null;
        $(input).on("change", function () {
            handleLotInput(timerLot, this);
        });
    });

    // Loop through each product's consumable lines
    item.consumable_lines.forEach((product) => {
        const lotLines = $(
            `#lot-selection-container-${product.product_id} .lot-selection`
        );
        if (lotLines.length > 0) {
            $(`#qty-${product.product_id}`).closest(".main_quantity").hide();
        } else {
            $(`#qty-${product.product_id}`).closest(".main_quantity").show();
        }
    });
}

function buildDetailsHtml(item) {
    let detailsHtml = `<div class="sample-header">
      <!-- div class="details-info"><span class="label">Name:</span> <span class="value">${item?.name}</span></div> </div> -->
      <div class="details-info"><span class="label">Lab request:</span> <span class="value">${item?.request_id}</span></div>
      <div class="details-info"><span class="label">PUID:</span> <span class="value">${item?.patient?.code}</span></div>
      <div class="details-info"><span class="label">Nom:</span> <span class="value">${item?.patient?.name}</span></div>
      <div class="details-info"><span class="label">Genre:</span> <span class="value">${item?.patient?.gender === "M" ? "Homme" : "Femme"}</span></div>
      <div class="details-info"><span class="label">Date de naissance:</span> <span class="value">${item?.patient?.birthday}</span></div>      
      <div class="details-info"><span class="label">Type Tube:</span> <span class="value">${item?.sample_type_id}</span></div>
      </div>
      <h4>Listes des consommables :</h4>
      <div class="product-wrapper">
        <div id="product_list">`;
    item.consumable_lines.forEach((product) => {
        detailsHtml += `
              <div class="product-item">
                <p><strong>${product.product_name}</strong></p>
                <div class="css_quantity main_quantity input-group" contenteditable="false">
                  <div class="input-group-prepend">
                    <a class="btn btn-secondary decrement-btn" aria-label="Supprimer" title="Supprimer" data-product-id="${product.product_id}" href="#">
                    -
                    </a>
                  </div>
                  <input type="text" class="form-control quantity" id="qty-${product.product_id}" value="${product.qty}" />
                  <div class="input-group-append">
                    <a class="btn btn-secondary increment-btn" aria-label="Ajouter" title="Ajouter" data-product-id="${product.product_id}" href="#">
                    +
                    </a>
                  </div>
                </div>
        
                <div id="lot-selection-container-${product.product_id}">
                  <div class="lot-selection-input">
                    <label for="lot-${product.product_id}" class="label-lot">Cliquer et Scanner le Numéros de lots/série </label>
                    <input type="text" class="form-control lot-input" id="lot-${product.product_id}" data-product-id="${product.product_id}" placeholder="Numéros de lots/série" />
                  </div>  
                </div>
              </div>
              `;
    });
    detailsHtml += "</div></div>";
    return detailsHtml;
}

function handleLotInput(timerLot, $input) {
    let incremented = false;
    if (timerLot) clearTimeout(timerLot);
    timerLot = setTimeout(() => {
        if (!incremented) {
            const productId = $input.dataset.productId;
            const lotValue = $input.value;
            const lotContainer = document.getElementById(
                `lot-selection-container-${productId}`
            );
            const existingLotElement = document.getElementById(
                `qty-${productId}-${lotValue}`
            );

            if (existingLotElement) {
                const currentQty = parseInt(existingLotElement.value, 10) || 0;
                existingLotElement.value = currentQty + 1;
                updateMainQuantity(productId);
            } else {
                const newLotHtml = `
            <div class="lot-selection" id="lot-selection-${productId}-${lotValue}">
              <div class="lot-section-info">
                <label for="lot-${productId}-${lotValue}">Numéros de lots/série: </label>
                <span class="lot-value" id="lot-${productId}-${lotValue}">${lotValue}</span></div>
              <div class="css_quantity lot_quantity input-group" contenteditable="false">
                <div class="input-group-prepend">
                  <a class="btn btn-secondary decrement-btn" aria-label="Supprimer" title="Supprimer" data-product-id="${productId}" data-lot-value="${lotValue}" href="#">
                  -
                  </a>
                </div>
                <input type="text" class="form-control quantity" id="qty-${productId}-${lotValue}" value="1" readonly />
                <div class="input-group-append">
                  <a class="btn btn-secondary increment-btn" aria-label="Ajouter" title="Ajouter" data-product-id="${productId}" data-lot-value="${lotValue}" href="#">
                  +
                  </a>
                </div>  
              </div>
              <button class="btn btn-primary-custom remove-btn" aria-label="Remove" title="Remove" data-product-id="${productId}" data-lot-value="${lotValue}">
                <i class="fa fa-trash"></i>
              </button>
            </div>`;

                lotContainer.insertAdjacentHTML("beforeend", newLotHtml);
                addEventListenersToButtons(productId, lotValue);
                updateMainQuantity(productId);
                toggleMainQuantityDisplay(productId);
            }

            incremented = true;
            $input.value = "";
        }
    }, 500);
}

function toggleMainQuantityDisplay(productId) {
    const lotLines = document.querySelectorAll(
        `#lot-selection-container-${productId} .lot-selection`
    );
    const mainQuantity = document
        .getElementById(`qty-${productId}`)
        .closest(".main_quantity");
    if (lotLines.length > 0) {
        mainQuantity.style.display = "none";
    } else {
        mainQuantity.style.display = "flex";
    }
}

function addEventListenersToButtons(productId, lotValue) {
    const incrementBtn = document.querySelector(
        `.increment-btn[data-product-id="${productId}"][data-lot-value="${lotValue}"]`
    );
    const decrementBtn = document.querySelector(
        `.decrement-btn[data-product-id="${productId}"][data-lot-value="${lotValue}"]`
    );

    const removeBtn = document.querySelector(
        `.remove-btn[data-product-id="${productId}"][data-lot-value="${lotValue}"]`
    );
    const qtyInput = document.getElementById(`qty-${productId}-${lotValue}`);

    if (incrementBtn && decrementBtn && removeBtn) {
        incrementBtn.addEventListener("click", (event) => {
            event.preventDefault();
            console.log('Test', incrementBtn.getAttribute('value'));
            const currentQty = parseInt(qtyInput.value, 10) || 0;
            qtyInput.value = currentQty + 1;
            updateMainQuantity(productId);
            toggleMainQuantityDisplay(productId);
        });

        decrementBtn.addEventListener("click", (event) => {
            event.preventDefault();
            const currentQty = parseInt(qtyInput.value, 10) || 0;
            if (currentQty > 1) {
                qtyInput.value = currentQty - 1;
                updateMainQuantity(productId);
                toggleMainQuantityDisplay(productId);
            } else {
                document
                    .getElementById(`lot-selection-${productId}-${lotValue}`)
                    .remove();
                updateMainQuantity(productId);
                toggleMainQuantityDisplay(productId);
            }
        });

        removeBtn.addEventListener("click", async (event) => {
            event.preventDefault();
            // if (!confirm("Voulez-vous supprimer?")) return;

            const confirmed = await showConfirm("Voulez-vous supprimer?");
            if (!confirmed) return;

            document
                .getElementById(`lot-selection-${productId}-${lotValue}`)
                .remove();
            updateMainQuantity(productId);
            toggleMainQuantityDisplay(productId);
        });
    }
}

function updateMainQuantity(productId) {
    let totalQty = 0;
    const lotQuantities = document.querySelectorAll(
        `#lot-selection-container-${productId} .quantity`
    );
    lotQuantities.forEach((input) => {
        totalQty += parseInt(input.value, 10) || 0;
    });

    const mainQtyInput = document.getElementById(`qty-${productId}`);
    mainQtyInput.value = totalQty;
}

function updateQuantity() {
    const productId = $(this).data("product-id");
    const qtyInput = $("#qty-" + productId);
    const currentQty = parseInt(qtyInput.val());

    if ($(this).hasClass("increment-btn")) {
        qtyInput.val(currentQty + 1);
    } else if (currentQty > 0) {
        qtyInput.val(currentQty - 1);
    }
}

function bindQuantityButtons() {
    $(".increment-btn").on("click", updateQuantity);
    $(".decrement-btn").on("click", updateQuantity);
}

function collectData(lab_request_ref) {
    if (localStorage.getItem("department_id")) {
        $.ajax({
            url: "/laboratory/collect_sample",
            type: "POST",
            contentType: "application/json",
            dataType: "json",
            data: JSON.stringify({ lab_request_ref }),
            beforeSend: showLoading,
            success: function (response) {
                if (response?.result?.status === "success") {
                    console.log('response', response.result.data);
                    renderElement(response.result.data);
                } else {
                    toastr.error(response?.error?.data?.message);
                }
            },
            error: function () {
                toastr.error('"Failed to collect sample"');
            },
            complete: hideLoading,
        });
    } else {
        $("#customModal").show();
    }
}

// Show loading spinner
function showLoading() {
    $("#loading_element").css("display", "flex");
    $("#loading-spinner").show();
}

function hideLoading() {
    $("#loading_element").hide();
    $("#loading-spinner").hide();
}

async function logout() {
    const activeSample = JSON.parse(localStorage.getItem("activeSample"));
    if (activeSample) {
        const confirmed = await showConfirm("Êtes-vous sûr de vouloir vous déconnecter ?");
        if (!confirmed) return;
    }
    showLoading();
    localStorage.removeItem("department_id");
    window.location.href = "/web/session/logout?redirect=/laboratory_sample_test";
}

function closeModal() {
    $("#close-btn").click(function () {
        $("#customModal").hide();
    });
}

$(document).ready(function () {
    console.log('lab_sample_screen.js loaded ------------------ ');

    const pageData = document.getElementById('pageData');

    let isDepartementClicked = false; // bouton pour checker l'ouverture du modal pour la selection de departement

    const departmentSelect = document.getElementById('departmentSelect');
    const savedDepartmentId = localStorage.getItem("department_id");
    const tokenInput = document.getElementById("tokenInput");
    const saveBtn = document.getElementById("save_collection_btn");
    const modal = document.getElementById("customModal");
    const tokenContainer = document.getElementById("tokenContainer");
    const departmentContainer = document.getElementById("departmentContainer");

    if (!pageData) {
        console.error("pageData element not found!");
        return;
    }

    let is_logged = pageData.dataset.isLogged === "true";

    let departments = [];
    if (pageData?.dataset?.departments) {
        try {
            departments = JSON.parse(pageData.dataset.departments);
        } catch (e) {
            console.error("Erreur JSON departments:", e);
        }
    } else {
        console.warn("departments dataset absent");
    }

    // toastr.options = {
    //     "closeButton": true,
    //     "debug": false,
    //     "newestOnTop": false,
    //     "progressBar": true,
    //     "positionClass": "toast-top-right",
    //     "preventDuplicates": false,
    //     "onclick": null,
    //     "showDuration": "300",
    //     "hideDuration": "1000",
    //     "timeOut": "5000",
    //     "extendedTimeOut": "1000",
    //     "showEasing": "swing",
    //     "hideEasing": "linear",
    //     "showMethod": "fadeIn",
    //     "hideMethod": "fadeOut"
    // };

    // REMPLISSAGE DEPARTEMENT SELECT par les départements reçus du serveur (filtrés par société)
    if (departmentSelect) {
        console.log('-------------//-Departments from dataset:', departments);
        if (Array.isArray(departments)) {
            departmentSelect.innerHTML = '';

            // Option par défaut
            // const defaultOption = document.createElement('option');
            // defaultOption.value = localStorage.getItem("department_id") || '';
            // defaultOption.textContent = '-- Sélectionner un département --';
            // defaultOption.disabled = true;
            // departmentSelect.appendChild(defaultOption);

            departments.forEach(dept => {
                const [id, name] = dept;

                const option = document.createElement('option');
                option.value = id;
                option.textContent = name;
                if (savedDepartmentId && savedDepartmentId == id) option.selected = true;
                departmentSelect.appendChild(option);
            });

        }
    }

    // console.log('Modal logic check: is_logged=', is_logged, ', savedDepartmentId=', savedDepartmentId);
    openModal(is_logged, isDepartementClicked, modal, tokenContainer, departmentContainer);
    updateDepartmentLabel();

    $("#save_collection_btn").on("click", function () {
        const selectedDepartment = $("#departmentSelect").val();
        const tokenInput = $("#tokenInput");
        const token = tokenInput.length ? tokenInput.val() : null;
        console.log("-----//-selectedDepartment", selectedDepartment);
        console.log("-----//-$(#departmentSelect).val()", $("#departmentSelect"));
        let is_finished = false;

        if (!is_logged) {

            // Pour utilisateur non connecté: login + département
            if (!token) {
                toastr.error("Veuillez Scannez votre code barre!");
                tokenInput.focus();
                return;
            }

            $.ajax({
                url: "/barcode/login",
                type: "POST",
                data: { token: token },
                success: function (response) {
                    if (!response.success) {
                        toastr.error(response.message || "Erreur d'authentification");
                        return;
                    }
                    if (response.success) {
                        is_logged = true;
                        toastr.success("Connexion réussie. Choisissez un département.");
                    }

                    console.log('-------------//-Departments from login response:', response.departments);
                    // remplir le select avec les départements reçus
                    if (response.departments && response.departments.length) {
                        $("#departmentSelect").empty();
                        // $("#departmentSelect").append(`<option value="" disabled selected>-- Sélectionner un département --</option>`);

                        response.departments.forEach(function (dept) {
                            $("#departmentSelect").append(
                                `<option value="${dept.id}">${dept.name}</option>`
                            );
                        });

                        $("#tokenContainer").hide();
                        $("#departmentContainer").show();
                        departmentContainer.style.display = "block";
                    }

                    console.log('-login response', response);
                    isDepartementClicked = false;
                    localStorage.setItem("department_id", selectedDepartment);
                    updateDepartmentLabel();
                    is_finished = true;
                },
                error: function () {
                    toastr.error("Erreur serveur");
                }
            });

        } else {
            console.log('Selected Department on Save:', selectedDepartment);
            if (!selectedDepartment || selectedDepartment === "null" || selectedDepartment === "") {
                toastr.error("Veuillez sélectionner un département !");
                return;
            }

            // Pour utilisateur déjà connecté: juste sauvegarder le département
            localStorage.setItem("department_id", selectedDepartment);
            isDepartementClicked = false;
            updateDepartmentLabel();
            document.getElementById("customModal").style.display = "none";
            is_logged = true;
            is_finished = true;
        }

        if (is_finished) {
            location.reload();
            is_finished = false;
        }
        console.log('-------------Selected Department ID:', selectedDepartment);
    });

    closeModal();

    $("#show_modal_prel").on("click", function () {
        isDepartementClicked = true;
        openModal(is_logged, isDepartementClicked, modal, tokenContainer, departmentContainer);
    });

    let timer = null;
    $("#search_input").focus();
    $("#search_input").on("change", function () {
        handleSearchInput(timer, $(this));
        $(this).focus();
    });

    checkAndDisableCollectButton();
    $("#collect").on("click", handleCollectButtonClick);
    $("#logout-button").on("click", logout);
});

function openModal(isLogged_check, isDepartementClicked, modal, tokenContainer, departmentContainer) {

    // Cacher tout au départ
    if (tokenContainer) tokenContainer.style.display = "none";
    if (departmentContainer) departmentContainer.style.display = "none";
    modal.style.display = "none";

    // ==============================
    // CAS 1 : connecté + déjà département → rien afficher
    // ==============================
    if (!isDepartementClicked && isLogged_check && localStorage.getItem("department_id")) {
        console.log('CAS 1: connecté + dept déjà choisi → modal caché');
        return;
    }

    // On affiche le modal
    modal.style.display = "flex";

    // ==============================
    // CAS 2 : NON connecté
    // ==============================
    if (!isLogged_check) {
        console.log('CAS 2: non connecté → afficher seulement token');
        if (tokenContainer) tokenContainer.style.display = "block";
        return; // 🔥 IMPORTANT → on ne montre PAS le département
    }

    // ==============================
    // CAS 3 : connecté (changement dept)
    // ==============================
    if (isLogged_check) {
        console.log('CAS 3: connecté → afficher département');
        if (departmentContainer) departmentContainer.style.display = "block";
    }
}

function updateDepartmentLabel() {
    const deptName = $("#departmentSelect option:selected").text();
    $("#show_modal_prel span.dept_name").remove();
    $("#show_modal_prel").append(
        `<span class="dept_name" style="margin-left:8px;">: ${deptName}</span>`
    );
}

function disableButton(saveBtnTmp) {
    saveBtnTmp.disabled = true;
    saveBtnTmp.style.opacity = "0.3";
    saveBtnTmp.style.pointerEvents = "none";
}

function enableButton(saveBtnTmp) {
    saveBtnTmp.disabled = false;
    saveBtnTmp.style.opacity = "1";
    saveBtnTmp.style.pointerEvents = "auto";
}

// Handle search input
function handleSearchInput(timer, $input) {
    $("#collect").prop("disabled", true);
    $("#sample_details").empty();

    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
        collectData($input.val());
        $input.val("");
        $input.blur();
        $input.focus();
        $("#error_message_for_stock").empty();
    }, 500);
}

// Crée le modal générique s'il n'existe pas encore
function ensureConfirmModalExists() {
    if (document.getElementById("genericConfirmModal")) return;

    const modalHtml = `
    <div id="genericConfirmModal" style="display:none;">
        <div class="modal-content" 
             style="background:white; padding:20px; border-radius:8px; text-align:center; max-width:400px;">
            <div class="modal-body">
                <p id="genericConfirmMessage">Êtes-vous sûr ?</p>
            </div>
            <div class="modal-footer" style="margin-top:20px;">
                <button id="genericConfirmNoBtn" class="btn btn-secondary" style="margin-right:10px;">NON</button>
                <button id="genericConfirmYesBtn" class="btn btn-primary-custom">OUI</button>
            </div>
        </div>
    </div>
    `;

    document.body.insertAdjacentHTML("beforeend", modalHtml);
}

// Affichage modal centré
function showGenericConfirmModal() {
    const modal = document.getElementById("genericConfirmModal");
    modal.style.display = "flex";
    modal.style.justifyContent = "center";
    modal.style.alignItems = "center";
    modal.style.position = "fixed";
    modal.style.top = "0";
    modal.style.left = "0";
    modal.style.width = "100%";
    modal.style.height = "100vh";
    modal.style.background = "#32323290";
    modal.style.zIndex = "9999";
}

// Masquer modal
function hideGenericConfirmModal() {
    const modal = document.getElementById("genericConfirmModal");
    modal.style.display = "none";
}

/**
 * showConfirm(message, title) => Promise<boolean>
 * Retourne true si OUI, false si NON
 */
function showConfirm(message) {
    return new Promise((resolve) => {
        ensureConfirmModalExists();

        // Mettre le texte
        document.getElementById("genericConfirmMessage").innerText = message;

        // Afficher modal
        showGenericConfirmModal();

        // Bouton NON
        const noBtn = document.getElementById("genericConfirmNoBtn");
        noBtn.onclick = () => {
            hideGenericConfirmModal();
            resolve(false);
        };

        // Bouton OUI
        const yesBtn = document.getElementById("genericConfirmYesBtn");
        yesBtn.onclick = () => {
            hideGenericConfirmModal();
            resolve(true);
        };
    });
}

// Handle collect button click
async function handleCollectButtonClick() {
    const activeSample = JSON.parse(localStorage.getItem("activeSample"));
    if (!activeSample) {
        toastr.error("Veuillez sélectionner ou scanner un code-barre.");
        return;
    }

    // if (!confirm("Vous êtes sûr de mettre à jour le consommable?")) return;

    const confirmed = await showConfirm("Vous êtes sûr de mettre à jour le consommable ?");
    if (!confirmed) return;

    const updatedConsumables = $(".product-item")
        .map(function () {
            const productId = $(this).find(".increment-btn").data("product-id");
            const mainQty = parseInt($(`#qty-${productId}`).val()) || 0;

            const lots = $(this)
                .find(".lot-selection")
                .map(function () {
                    const lotValue = $(this).find(".lot-value").text();
                    const qty = parseInt($(this).find(".quantity").val());
                    if (lotValue) {
                        return {
                            lot: lotValue,
                            qty: qty,
                        };
                    }
                })
                .get();

            return {
                product_id: productId,
                main_qty: mainQty,
                lots: lots,
            };
        })
        .get();
    // const savedCollectionId = localStorage.getItem("collection_center_id");
    const savedDepartmentId = localStorage.getItem("department_id");
    console.log('updatedConsumables', updatedConsumables);
    console.log('savedDepartmentId', savedDepartmentId);
    updateConsumables(activeSample.id, updatedConsumables, savedDepartmentId);
}

// Update consumables on the server
function updateConsumables(sampleId, consumables, savedDepartmentId) {
    const ex_collect_checkbox = $("#ex_collect_checkbox").is(":checked");
    $.ajax({
        url: "/laboratory/update_consumables",
        type: "POST",
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify({
            sample_id: sampleId,
            consumables: consumables,
            department_id: Number(savedDepartmentId),
            ex_collect_checkbox,
        }),
        beforeSend: showLoading,
        success: function (response) {
            console.log('update response', response);
            if (response?.result?.status === "success") {
                toastr.success(
                    response.result.message || "Consommables mis à jour avec succès!"
                );
                $(".sample_item.active").remove();
                $("#sample_details").empty();
                $("#error_message_for_stock").empty();
            } else {
                // toastr.error(response?.error?.data?.message);
                error_message = response?.error?.data?.message || "Erreur de mise à jour";
                $("#error_message_for_stock").text("⚠️ " + error_message);
            }
        },
        error: function () {
            toastr.error("Il y a Erreur de Mise à jour");
        },
        complete: hideLoading,
    });
}