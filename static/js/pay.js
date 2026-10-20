(function () {
    var root = document.querySelector("[data-pay]");
    if (!root) return;

    var button = document.querySelector("[data-pay-button]");
    var message = document.querySelector("[data-pay-message]");
    var csrf = document.querySelector("[name=csrfmiddlewaretoken]");

    function show(text) {
        if (message) { message.textContent = text; message.hidden = false; }
    }

    function confirmPayment(response) {
        show("Confirming your payment. Please do not close this page.");
        var body = new FormData();
        body.append("razorpay_order_id", response.razorpay_order_id);
        body.append("razorpay_payment_id", response.razorpay_payment_id);
        body.append("razorpay_signature", response.razorpay_signature);
        fetch(root.dataset.verifyUrl, {
            method: "POST",
            body: body,
            headers: { "X-CSRFToken": csrf ? csrf.value : "" },
            credentials: "same-origin"
        })
            .then(function (reply) { return reply.json(); })
            .then(function (data) { window.location.href = data.redirect || root.dataset.failedUrl; })
            .catch(function () { window.location.href = root.dataset.failedUrl; });
    }

    function open() {
        if (typeof Razorpay === "undefined") {
            show("The payment window could not load. Check your connection and try again.");
            return;
        }
        var checkout = new Razorpay({
            key: root.dataset.key,
            amount: root.dataset.amount,
            currency: "INR",
            name: "ProjectVybe",
            description: root.dataset.description,
            order_id: root.dataset.orderId,
            prefill: {
                name: root.dataset.name,
                email: root.dataset.email,
                contact: root.dataset.contact
            },
            theme: { color: "#16294a" },
            handler: confirmPayment,
            modal: {
                ondismiss: function () { show("Payment was not completed. You can try again."); }
            }
        });
        checkout.on("payment.failed", function () {
            window.location.href = root.dataset.failedUrl;
        });
        checkout.open();
    }

    if (button) button.addEventListener("click", open);
    window.addEventListener("load", open);
})();
