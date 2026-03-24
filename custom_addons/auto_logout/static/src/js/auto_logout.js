odoo.define('auto_logout.AutoLogout', function (require) {
    "use strict";

    var WebClient = require('web.WebClient');
    var rpc = require('web.rpc');
    var Dialog = require('web.Dialog');
    var core = require('web.core');
    var session = require('web.session');
    var _t = core._t;

    WebClient.include({

        init: function () {
            console.debug("-----Auto logout: init");
            this._super.apply(this, arguments);
            this._autoLogoutSetup();
        },

        start: function () {
            console.log("-----Auto logout: start");
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._autoLogoutSetup();
            });
        },

        // ======================================================
        // MAIN SETUP
        // ======================================================
        _autoLogoutSetup: function () {
            console.debug("-----Auto logout: setup");
            var self = this;

            if (this._autoLogoutSetupDone) {
                return;
            }
            this._autoLogoutSetupDone = true;

            // -----------------------------
            // TAB MANAGEMENT SYSTEM
            // -----------------------------
            this._setupTabDetection();

            // -----------------------------
            // READ TIMEOUT PARAM
            // -----------------------------
            var timeoutMinutes = 30; // default

            rpc.query({
                model: 'auto_logout.config',
                method: 'get_auto_logout_minutes',
                args: [],
            }).then(function (value) {

                if (value) {
                    var parsed = parseInt(value, 10);
                    if (!isNaN(parsed) && parsed > 0) {
                        timeoutMinutes = parsed;
                    }
                }

                if (!timeoutMinutes || timeoutMinutes <= 0) {
                    return;
                }

                // Exclude admin
                session.user_has_group('base.group_system').then(function (isAdmin) {
                    if (isAdmin) {
                        return;
                    }
                    self._startIdleTimer(timeoutMinutes);
                });

            }).catch(function () {
                console.warn("Auto logout: unable to read parameter.");
            });
        },

        // ======================================================
        // TAB DETECTION SYSTEM
        // ======================================================
        _setupTabDetection: function () {
            console.log("-----Auto logout: setup tab detection");

            var STORAGE_KEY = "odoo_open_tabs";
            var TIMEOUT = 15000; // 15 sec

            // 🔴 TOUJOURS générer un nouvel ID (même si duplication)
            var tabId = Date.now() + "_" + Math.random();
            sessionStorage.setItem('odoo_tab_id', tabId);

            function registerTab() {
                var tabs = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
                tabs[tabId] = Date.now();
                localStorage.setItem(STORAGE_KEY, JSON.stringify(tabs));
            }

            function cleanDeadTabs() {
                var tabs = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
                var now = Date.now();

                Object.keys(tabs).forEach(function (id) {
                    if (now - tabs[id] > TIMEOUT) {
                        delete tabs[id];
                    }
                });

                localStorage.setItem(STORAGE_KEY, JSON.stringify(tabs));
                return tabs;
            }

            // Register immediately
            registerTab();

            // Heartbeat
            setInterval(function () {
                registerTab();
            }, 5000);

            // Check multi-tabs
            setTimeout(function () {
                var tabs = cleanDeadTabs();
                var count = Object.keys(tabs).length;
                console.log("Active tabs:", count);

                if (count > 1) {
                    console.warn("⚠ Odoo opened in multiple tabs");
                }
            }, 1000);

            // Clean on close
            window.addEventListener('beforeunload', function () {
                var tabs = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
                delete tabs[tabId];
                localStorage.setItem(STORAGE_KEY, JSON.stringify(tabs));
            });
        },


        // ======================================================
        // IDLE TIMER SYSTEM
        // ======================================================
        _startIdleTimer: function (minutes) {

            var self = this;
            var idleMs = minutes * 60 * 1000;
            var warnBeforeMs = 30000; // 30 sec avant logout
            var CHECK_INTERVAL = 5000; // vérifie toutes les 5 sec

            var warnDialog = null;
            var dialogActive = false;

            var ACTIVITY_KEY = "odoo_last_activity";

            // -----------------------------
            // Marquer activité globale
            // -----------------------------
            function markActivity() {
                localStorage.setItem(ACTIVITY_KEY, Date.now());
            }

            // -----------------------------
            // Warning dialog
            // -----------------------------
            function showWarning(remainingMs) {

                if (warnDialog) {
                    try { warnDialog.close(); } catch (e) { }
                }

                dialogActive = true;

                warnDialog = new Dialog(self, {
                    title: "Déconnexion pour inactivité",
                    size: 'small',
                    $content: $('<div/>').text(
                        "Vous serez déconnecté dans " + Math.ceil(remainingMs / 1000) +
                        " secondes en raison de l'inactivité."
                    ),
                    buttons: [{
                        text: "Rester connecté",
                        classes: 'btn-primary',
                        click: function () {
                            dialogActive = false;
                            markActivity();
                            try { warnDialog.close(); } catch (e) { }
                        },
                    }],
                });

                warnDialog.open();
            }

            // -----------------------------
            // Logout global
            // -----------------------------
            function doLogout() {

                // Vérifier qu'il n'y a vraiment aucune activité récente
                var last = parseInt(localStorage.getItem(ACTIVITY_KEY) || 0);
                var now = Date.now();

                if (now - last < idleMs) {
                    return; // activité ailleurs
                }

                session.session_logout().then(function () {
                    window.location.href = '/web/login';
                }).catch(function () {
                    window.location.href = '/web/login';
                });
            }

            // -----------------------------
            // Vérification périodique
            // -----------------------------
            function checkGlobalIdle() {

                var last = parseInt(localStorage.getItem(ACTIVITY_KEY) || 0);
                var now = Date.now();
                var diff = now - last;

                if (!last) {
                    markActivity();
                    return;
                }

                // Si on approche du timeout
                if (diff >= (idleMs - warnBeforeMs) && diff < idleMs) {

                    if (!dialogActive) {
                        showWarning(idleMs - diff);
                    }

                } else {

                    // activité détectée ailleurs → fermer dialog
                    if (warnDialog) {
                        try { warnDialog.close(); } catch (e) { }
                        warnDialog = null;
                        dialogActive = false;
                    }
                }

                if (diff >= idleMs) {
                    doLogout();
                }
            }

            // -----------------------------
            // Synchronisation entre onglets
            // -----------------------------
            window.addEventListener("storage", function (event) {
                if (event.key === ACTIVITY_KEY) {
                    // activité dans un autre onglet
                    if (warnDialog) {
                        try { warnDialog.close(); } catch (e) { }
                        warnDialog = null;
                        dialogActive = false;
                    }
                }
            });

            // -----------------------------
            // Événements utilisateur
            // -----------------------------
            ['mousemove', 'keydown', 'click', 'touchstart']
                .forEach(function (ev) {
                    document.addEventListener(ev, markActivity, { passive: true });
                });

            // Initialiser activité
            markActivity();

            // Lancer vérification périodique
            setInterval(checkGlobalIdle, CHECK_INTERVAL);
        },

    });
});
