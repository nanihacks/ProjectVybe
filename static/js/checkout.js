(function () {
    var total = document.querySelector("[data-order-total]");
    var lines = document.querySelector("[data-order-lines]");
    var boxes = document.querySelectorAll("[data-checkout-form] input[name='addons']");
    if (!total || !boxes.length) return;

    var base = parseFloat(total.getAttribute("data-base")) || 0;
    var firstLine = lines ? lines.firstElementChild : null;

    function rupees(value) {
        var hasPaise = Math.round(value * 100) % 100 !== 0;
        return "₹" + value.toLocaleString("en-IN", {
            minimumFractionDigits: hasPaise ? 2 : 0,
            maximumFractionDigits: 2
        });
    }

    function update() {
        var sum = base;
        if (lines && firstLine) {
            while (lines.lastElementChild !== firstLine) lines.removeChild(lines.lastElementChild);
        }
        boxes.forEach(function (box) {
            if (!box.checked) return;
            var price = parseFloat(box.getAttribute("data-price")) || 0;
            sum += price;
            if (lines) {
                var item = document.createElement("li");
                var name = document.createElement("span");
                var amount = document.createElement("strong");
                name.textContent = box.getAttribute("data-name") || "Add-on";
                amount.textContent = price === 0 ? "Included" : rupees(price);
                item.appendChild(name);
                item.appendChild(amount);
                lines.appendChild(item);
            }
        });
        total.textContent = rupees(sum);
    }

    boxes.forEach(function (box) { box.addEventListener("change", update); });
    update();
})();
