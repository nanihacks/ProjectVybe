(function () {
    const toggle = document.querySelector(".menu-toggle");
    const navigation = document.querySelector(".site-navigation");
    const projectsDropdown = document.querySelector(".site-navigation__dropdown");
    const projectsToggle = document.querySelector(".site-navigation__dropdown-toggle");

    if (!toggle || !navigation) return;

    const closeNavigation = function () {
        navigation.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
    };

    const closeProjectsDropdown = function () {
        if (!projectsDropdown || !projectsToggle) return;
        projectsDropdown.classList.remove("is-open");
        projectsToggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", function () {
        closeProjectsDropdown();
        const isOpen = navigation.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });

    if (projectsDropdown && projectsToggle) {
        projectsToggle.addEventListener("click", function () {
            const isOpen = projectsDropdown.classList.toggle("is-open");
            projectsToggle.setAttribute("aria-expanded", String(isOpen));
        });

    }

    navigation.addEventListener("click", function (event) {
        if (event.target.closest("a")) {
            closeProjectsDropdown();
            closeNavigation();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            const dropdownWasOpen = projectsDropdown && projectsDropdown.classList.contains("is-open");
            closeProjectsDropdown();
            closeNavigation();
            if (dropdownWasOpen && projectsToggle) {
                projectsToggle.focus();
            } else {
                toggle.focus();
            }
        }
    });

    document.addEventListener("click", function (event) {
        if (!navigation.contains(event.target) && !toggle.contains(event.target)) {
            closeProjectsDropdown();
            closeNavigation();
        }
    });
})();

(function () {
    const modal = document.querySelector("[data-project-search-modal]");
    const modalForm = modal?.querySelector("[data-project-search-form]");
    const modalInput = modal?.querySelector("[data-project-search-input]");
    const resultsContainer = modal?.querySelector("[data-project-search-results]");
    const status = modal?.querySelector("[data-project-search-status]");
    const navForms = Array.from(document.querySelectorAll("[data-nav-search]"));
    const navInputs = navForms
        .map(function (form) { return form.querySelector("input[type='search']"); })
        .filter(Boolean);
    const searchUrl = modal?.dataset.projectSearchUrl;

    if (!modal || !modalForm || !modalInput || !resultsContainer || !status || !searchUrl) return;

    let previouslyFocusedElement = null;
    let debounceTimer = null;
    let requestController = null;

    const setStatus = function (message) {
        status.textContent = message;
    };

    const resetNavSearch = function () {
        navForms.forEach(function (navForm) {
            navForm.classList.remove("is-expanded");
            const navInput = navForm.querySelector("input[type='search']");
            const navButton = navForm.querySelector("[data-nav-search-button]");
            if (navInput) navInput.value = "";
            if (navButton) navButton.setAttribute("aria-label", "Open project search");
        });
    };

    const closeSearch = function (event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("is-project-search-open");
        if (requestController) requestController.abort();
        modalInput.value = "";
        resultsContainer.replaceChildren();
        setStatus("Start typing to find a project.");
        resetNavSearch();

        const originatingForm = previouslyFocusedElement?.closest?.("[data-nav-search]");
        const originatingButton = originatingForm?.querySelector("[data-nav-search-button]");
        if (originatingButton) {
            originatingButton.focus();
        } else if (previouslyFocusedElement) {
            previouslyFocusedElement.focus();
        }
        previouslyFocusedElement = null;
    };

    const openSearch = function (focusModalInput) {
        if (modal.hidden) {
            previouslyFocusedElement = document.activeElement;
            modal.hidden = false;
            modal.setAttribute("aria-hidden", "false");
            document.body.classList.add("is-project-search-open");
        }
        if (focusModalInput) modalInput.focus();
    };

    const renderResults = function (results) {
        resultsContainer.replaceChildren();

        results.forEach(function (project) {
            const link = document.createElement("a");
            link.className = "project-search-result";
            link.href = project.url;

            if (project.image_url) {
                const image = document.createElement("img");
                image.className = "project-search-result__image";
                image.src = project.image_url;
                image.alt = project.title + " thumbnail";
                image.loading = "lazy";
                image.decoding = "async";
                link.appendChild(image);
            } else {
                const placeholder = document.createElement("span");
                placeholder.className = "project-search-result__image project-search-result__placeholder";
                placeholder.setAttribute("aria-hidden", "true");
                placeholder.textContent = "Project";
                link.appendChild(placeholder);
            }

            const content = document.createElement("span");
            content.className = "project-search-result__content";

            const category = document.createElement("span");
            category.className = "project-search-result__category";
            category.textContent = project.category;
            content.appendChild(category);

            const title = document.createElement("strong");
            title.className = "project-search-result__title";
            title.textContent = project.title;
            content.appendChild(title);

            const description = document.createElement("span");
            description.className = "project-search-result__description";
            description.textContent = project.description;
            content.appendChild(description);

            if (project.technology) {
                const technology = document.createElement("span");
                technology.className = "project-search-result__technology";
                technology.textContent = project.technology;
                content.appendChild(technology);
            }

            link.appendChild(content);
            resultsContainer.appendChild(link);
        });
    };

    const searchProjects = function (value) {
        const query = value.trim();
        if (requestController) requestController.abort();
        if (!query) {
            resultsContainer.replaceChildren();
            setStatus("Start typing to find a project.");
            return;
        }
        if (query.length < 2) {
            resultsContainer.replaceChildren();
            setStatus("Type at least 2 characters to search.");
            return;
        }

        requestController = new AbortController();
        setStatus("Searching projects...");
        fetch(searchUrl + "?q=" + encodeURIComponent(query), {
            headers: { "Accept": "application/json" },
            signal: requestController.signal,
        })
            .then(function (response) {
                if (response.status === 429) {
                    const limited = new Error("Search rate limited");
                    limited.rateLimited = true;
                    throw limited;
                }
                if (!response.ok) throw new Error("Project search failed");
                return response.json();
            })
            .then(function (data) {
                if (data.results.length) {
                    setStatus(
                        data.results.length +
                        " project" +
                        (data.results.length === 1 ? "" : "s") +
                        " found"
                    );
                    renderResults(data.results);
                } else {
                    resultsContainer.replaceChildren();
                    setStatus("No projects found for \"" + query + "\".");
                }
            })
            .catch(function (error) {
                if (error.name === "AbortError") return;
                resultsContainer.replaceChildren();
                setStatus(
                    error.rateLimited
                        ? "Too many searches. Please wait a moment and try again."
                        : "Project search is temporarily unavailable."
                );
            });
    };

    const scheduleSearch = function (value) {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(function () {
            searchProjects(value);
        }, 220);
    };

    const syncAndOpen = function (value, focusModalInput) {
        const query = value || "";
        modalInput.value = query;
        openSearch(focusModalInput);
        scheduleSearch(query);
    };

    const syncNavInputs = function (value) {
        navInputs.forEach(function (input) {
            input.value = value;
        });
    };

    navForms.forEach(function (navForm) {
        const navInput = navForm.querySelector("input[type='search']");
        const navButton = navForm.querySelector("[data-nav-search-button]");
        if (!navInput) return;

        if (navButton) {
            navButton.addEventListener("click", function (event) {
                event.preventDefault();
                syncNavInputs(navInput.value);
                syncAndOpen(navInput.value, true);
            });
        }

        navInput.addEventListener("input", function () {
            syncNavInputs(navInput.value);
            syncAndOpen(navInput.value, false);
        });

        navForm.addEventListener("submit", function (event) {
            event.preventDefault();
            syncNavInputs(navInput.value);
            syncAndOpen(navInput.value, true);
        });
    });

    modalInput.addEventListener("input", function () {
        syncNavInputs(modalInput.value);
        scheduleSearch(modalInput.value);
    });

    modalForm.addEventListener("submit", function (event) {
        event.preventDefault();
        searchProjects(modalInput.value);
    });

    modal.addEventListener("click", function (event) {
        const closeTarget = event.target.closest("[data-project-search-close]");
        if (closeTarget && modal.contains(closeTarget)) closeSearch(event);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !modal.hidden) closeSearch();
    });
})();

(function () {
    const form = document.querySelector(".project-enquiry-form");
    if (!form) return;

    const steps = Array.from(form.querySelectorAll("[data-enquiry-step]"));
    const nextButton = form.querySelector("[data-enquiry-next]");
    const backButton = form.querySelector("[data-enquiry-back]");
    const modalTitle = form.closest(".enquiry-modal")?.querySelector("[data-enquiry-modal-title]");
    const modalProgress = form.closest(".enquiry-modal")?.querySelector("[data-enquiry-progress]");
    const startStep = Number(form.dataset.startStep) === 2 ? 2 : 1;

    const showStep = function (stepNumber) {
        steps.forEach(function (step) {
            const isCurrent = Number(step.dataset.enquiryStep) === stepNumber;
            step.hidden = !isCurrent;
            step.setAttribute("aria-hidden", String(!isCurrent));
        });

        if (modalTitle) {
            modalTitle.textContent = stepNumber === 2 ? "Add-ons and message" : "Your details";
        }
        const stepLabel = form.closest(".enquiry-modal")?.querySelector("[data-enquiry-step-label]");
        if (stepLabel) {
            stepLabel.textContent = "Step " + stepNumber + " of 2";
        }
        if (modalProgress) {
            modalProgress.style.width = stepNumber === 2 ? "100%" : "50%";
        }
    };

    if (nextButton) {
        nextButton.addEventListener("click", function () {
            const firstStep = form.querySelector('[data-enquiry-step="1"]');
            const requiredFields = firstStep.querySelectorAll("input[required], select[required], textarea[required]");

            for (const field of requiredFields) {
                if (!field.checkValidity()) {
                    field.reportValidity();
                    return;
                }
            }

            showStep(2);
        });
    }

    if (backButton) {
        backButton.addEventListener("click", function () {
            showStep(1);
        });
    }

    showStep(startStep);
})();

(function () {
    const modal = document.querySelector(".enquiry-modal");
    const openers = document.querySelectorAll("[data-enquiry-open]");
    if (!modal || !openers.length) return;

    const firstField = modal.querySelector("input:not([type='hidden'])");
    let previouslyFocusedElement = null;

    const closeModal = function (event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("is-modal-open");
        if (previouslyFocusedElement) previouslyFocusedElement.focus();
    };

    openers.forEach(function (opener) {
        opener.addEventListener("click", function (event) {
            event.preventDefault();
            previouslyFocusedElement = opener;
            modal.hidden = false;
            modal.setAttribute("aria-hidden", "false");
            document.body.classList.add("is-modal-open");
            if (firstField) firstField.focus();
        });
    });

    modal.addEventListener("click", function (event) {
        const closeTarget = event.target.closest("[data-enquiry-close]");
        if (closeTarget && modal.contains(closeTarget)) closeModal(event);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !modal.hidden) closeModal();
    });
})();

(function () {
    const modal = document.querySelector("[data-video-modal]");
    const openers = document.querySelectorAll("[data-video-open]");
    const frame = modal?.querySelector("[data-video-frame]");
    const modalTitle = modal?.querySelector("[data-video-modal-title]");

    if (!modal || !openers.length || !frame) return;

    let previouslyFocusedElement = null;

    const closeVideo = function (event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        frame.removeAttribute("src");
        document.body.classList.remove("is-video-modal-open");
        if (previouslyFocusedElement) previouslyFocusedElement.focus();
    };

    openers.forEach(function (opener) {
        opener.addEventListener("click", function () {
            const videoUrl = opener.dataset.videoUrl;
            if (!videoUrl) return;

            previouslyFocusedElement = opener;
            frame.src = `${videoUrl}&autoplay=1`;
            frame.title = `${opener.dataset.videoTitle || "Project"} demo`;
            if (modalTitle) modalTitle.textContent = `${opener.dataset.videoTitle || "Project"} demo`;
            modal.hidden = false;
            modal.setAttribute("aria-hidden", "false");
            document.body.classList.add("is-video-modal-open");
        });
    });

    modal.addEventListener("click", function (event) {
        const closeTarget = event.target.closest("[data-video-close]");
        if (closeTarget && modal.contains(closeTarget)) closeVideo(event);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !modal.hidden) closeVideo();
    });
})();

(function () {
    const carousels = document.querySelectorAll("[data-category-carousel], [data-service-carousel], [data-review-carousel]");
    if (!carousels.length) return;

    carousels.forEach(function (carousel) {
        const prefix = carousel.hasAttribute("data-service-carousel")
            ? "service"
            : carousel.hasAttribute("data-review-carousel")
                ? "review"
                : "category";
        const scroller = carousel.querySelector(`[data-${prefix}-scroller]`);
        const track = carousel.querySelector(".category-carousel__track");
        const previousButton = carousel.querySelector(`[data-${prefix}-prev]`);
        const nextButton = carousel.querySelector(`[data-${prefix}-next]`);
        const dotsContainer = carousel.querySelector(`[data-${prefix}-dots]`);
        const currentIndicator = carousel.querySelector(`[data-${prefix}-current]`);
        const totalIndicator = carousel.querySelector(`[data-${prefix}-total]`);
        const cardSelector = prefix === "service"
            ? ".card--service"
            : prefix === "review"
                ? ".review-card"
                : ".card--category";
        if (!scroller || !track || !previousButton || !nextButton) return;

        const getGap = function () {
            const trackStyles = window.getComputedStyle(track);
            return parseFloat(trackStyles.columnGap || trackStyles.gap) || 0;
        };

        const getScrollStep = function () {
            const card = track.querySelector(cardSelector);
            if (!card) return scroller.clientWidth;
            return card.getBoundingClientRect().width + getGap();
        };

        // The counter and dots count pages (a screenful of cards), not scroll positions.
        const getCardsPerView = function () {
            const step = getScrollStep();
            if (!step) return 1;
            return Math.max(1, Math.floor((scroller.clientWidth + getGap()) / step + 0.01));
        };

        const getSlideCount = function () {
            const cardCount = track.querySelectorAll(cardSelector).length;
            return Math.max(1, Math.ceil(cardCount / getCardsPerView()));
        };

        const getCurrentSlide = function () {
            const step = getScrollStep();
            const slideCount = getSlideCount();
            const maximumScroll = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
            if (!step) return 0;
            if (maximumScroll > 0 && scroller.scrollLeft >= maximumScroll - 1) return slideCount - 1;
            return Math.min(
                slideCount - 1,
                Math.max(0, Math.round(scroller.scrollLeft / (step * getCardsPerView())))
            );
        };

        const renderDots = function (slideCount) {
            if (!dotsContainer) return;

            dotsContainer.replaceChildren();
            for (let index = 0; index < slideCount; index += 1) {
                const dot = document.createElement("button");
                dot.type = "button";
                dot.className = "category-carousel__dot";
                dot.setAttribute("role", "tab");
                dot.setAttribute("aria-label", `Go to ${prefix} page ${index + 1}`);
                dot.addEventListener("click", function () {
                    const maximumScroll = scroller.scrollWidth - scroller.clientWidth;
                    const target = Math.min(maximumScroll, index * getCardsPerView() * getScrollStep());
                    scroller.scrollTo({ left: target, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
                });
                dotsContainer.appendChild(dot);
            }
        };

        let renderedSlideCount = 0;

        const updateControls = function () {
            const maximumScroll = scroller.scrollWidth - scroller.clientWidth;
            previousButton.disabled = scroller.scrollLeft <= 1;
            nextButton.disabled = scroller.scrollLeft >= maximumScroll - 1;

            const slideCount = getSlideCount();
            if (slideCount !== renderedSlideCount) {
                renderDots(slideCount);
                renderedSlideCount = slideCount;
            }

            const currentSlide = getCurrentSlide();
            const currentText = String(currentSlide + 1).padStart(2, "0");
            const totalText = String(slideCount).padStart(2, "0");
            // Only touch the DOM when the value changes, so scrolling stays cheap.
            if (currentIndicator && currentIndicator.textContent !== currentText) currentIndicator.textContent = currentText;
            if (totalIndicator && totalIndicator.textContent !== totalText) totalIndicator.textContent = totalText;
            if (dotsContainer) {
                Array.from(dotsContainer.children).forEach(function (dot, index) {
                    const isActive = index === currentSlide;
                    dot.classList.toggle("is-active", isActive);
                    dot.setAttribute("aria-selected", String(isActive));
                });
            }
        };

        const moveCarousel = function (direction) {
            const maximumScroll = scroller.scrollWidth - scroller.clientWidth;
            const nextPosition = Math.min(
                maximumScroll,
                Math.max(0, scroller.scrollLeft + direction * getScrollStep())
            );

            scroller.scrollTo({ left: nextPosition, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
            window.setTimeout(updateControls, 250);
        };

        previousButton.addEventListener("click", function () {
            moveCarousel(-1);
        });

        nextButton.addEventListener("click", function () {
            moveCarousel(1);
        });

        scroller.addEventListener("scroll", updateControls, { passive: true });
        window.addEventListener("resize", updateControls);
        updateControls();
    });
})();


// Announcement bar: remember a dismissal for that exact text (per browser).
(function () {
    const bar = document.querySelector("[data-announcement]");
    if (!bar) return;

    const storageKey = "projectvybe-announcement-dismissed";
    const announcementKey = bar.dataset.announcementKey || "";

    try {
        if (window.localStorage.getItem(storageKey) === announcementKey) {
            bar.hidden = true;
            return;
        }
    } catch (error) {
        // Storage can be blocked; the bar simply stays visible.
    }

    const closeButton = bar.querySelector("[data-announcement-close]");
    if (!closeButton) return;
    closeButton.addEventListener("click", function () {
        bar.hidden = true;
        try {
            window.localStorage.setItem(storageKey, announcementKey);
        } catch (error) {
            // Ignore: dismissal just will not be remembered.
        }
    });
})();


// Scroll reveals: elements with data-reveal fade in once as they enter the view.
// Content is visible without JavaScript, with reduced motion, and in print.
(function () {
    const targets = document.querySelectorAll("[data-reveal]");
    if (!targets.length) return;

    const revealAll = function () {
        targets.forEach(function (element) {
            element.classList.add("is-revealed");
        });
    };

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || !("IntersectionObserver" in window)) {
        revealAll();
        return;
    }

    targets.forEach(function (element) {
        if (element.getAttribute("data-reveal") === "stagger") {
            Array.prototype.forEach.call(element.children, function (child, index) {
                child.style.setProperty("--reveal-i", Math.min(index, 6));
            });
        }
    });

    const observer = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-revealed");
                observer.unobserve(entry.target);
            });
        },
        { rootMargin: "0px 0px -10% 0px", threshold: 0.05 }
    );
    targets.forEach(function (element) {
        observer.observe(element);
    });

    // Safety net: never leave content hidden if the observer does not fire.
    window.setTimeout(revealAll, 4000);
})();


// Project page: tick add-ons, see the total, and carry the choice to checkout.
(function () {
    const root = document.querySelector("[data-addons][data-checkout-url]");
    if (!root) return;

    const boxes = root.querySelectorAll(".addon2__input");
    const totalElement = root.querySelector("[data-addons-total]");
    const countElement = root.querySelector("[data-addons-count]");
    const continueLink = root.querySelector("[data-addons-continue]");
    const base = parseFloat(root.getAttribute("data-base-price")) || 0;
    const checkoutUrl = root.getAttribute("data-checkout-url");
    const buyLinks = document.querySelectorAll("[data-checkout-link]");

    function rupees(value) {
        const hasPaise = Math.round(value * 100) % 100 !== 0;
        return "₹" + value.toLocaleString("en-IN", {
            minimumFractionDigits: hasPaise ? 2 : 0,
            maximumFractionDigits: 2
        });
    }

    function update() {
        const ids = [];
        let sum = base;
        boxes.forEach(function (box) {
            if (box.checked) {
                ids.push(box.value);
                sum += parseFloat(box.getAttribute("data-price")) || 0;
            }
        });
        const href = ids.length
            ? checkoutUrl + "?" + ids.map(function (id) { return "addons=" + encodeURIComponent(id); }).join("&")
            : checkoutUrl;
        if (totalElement) totalElement.textContent = rupees(sum);
        if (countElement) countElement.textContent = ids.length ? "project + " + ids.length + " add-on" + (ids.length > 1 ? "s" : "") : "project only";
        if (continueLink) continueLink.setAttribute("href", href);
        buyLinks.forEach(function (link) { link.setAttribute("href", href); });
    }

    boxes.forEach(function (box) { box.addEventListener("change", update); });
    update();
})();

(function () {
    const bar = document.querySelector("[data-pd-sticky]");
    const card = document.querySelector(".pd-card");
    if (!bar || !card || !("IntersectionObserver" in window)) return;

    const footer = document.querySelector(".site-footer");
    let cardVisible = true;
    let footerVisible = false;
    const focusable = bar.querySelectorAll("a, button");

    const update = function () {
        const show = !cardVisible && !footerVisible;
        bar.classList.toggle("is-visible", show);
        bar.setAttribute("aria-hidden", String(!show));
        focusable.forEach(function (item) {
            item.tabIndex = show ? 0 : -1;
        });
    };

    new IntersectionObserver(function (entries) {
        cardVisible = entries[entries.length - 1].isIntersecting;
        update();
    }).observe(card);

    if (footer) {
        new IntersectionObserver(function (entries) {
            footerVisible = entries[entries.length - 1].isIntersecting;
            update();
        }).observe(footer);
    }
})();

(function () {
    document.querySelectorAll("[data-gallery]").forEach(function (gallery) {
        const track = gallery.querySelector("[data-gallery-track]");
        const prev = gallery.querySelector("[data-gallery-prev]");
        const next = gallery.querySelector("[data-gallery-next]");
        const count = gallery.querySelector("[data-gallery-count]");
        const dotsBox = gallery.querySelector("[data-gallery-dots]");
        if (!track || !prev || !next) return;

        const items = Array.from(track.children);
        const dots = items.map(function (item, index) {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.className = "pd-gallery__dot";
            dot.setAttribute("aria-label", "Show image " + (index + 1));
            dot.addEventListener("click", function () {
                track.scrollTo({ left: item.offsetLeft - items[0].offsetLeft });
            });
            if (dotsBox) dotsBox.appendChild(dot);
            return dot;
        });

        const currentIndex = function () {
            let best = 0;
            let bestDistance = Infinity;
            items.forEach(function (item, index) {
                const distance = Math.abs(item.offsetLeft - items[0].offsetLeft - track.scrollLeft);
                if (distance < bestDistance) {
                    bestDistance = distance;
                    best = index;
                }
            });
            return best;
        };

        const update = function () {
            const max = track.scrollWidth - track.clientWidth - 2;
            prev.disabled = track.scrollLeft <= 2;
            next.disabled = track.scrollLeft >= max;
            const atEnd = track.scrollLeft >= max;
            const index = atEnd ? items.length - 1 : currentIndex();
            dots.forEach(function (dot, i) {
                dot.classList.toggle("is-active", i === index);
                dot.setAttribute("aria-current", i === index ? "true" : "false");
            });
            if (count) count.textContent = index + 1 + " / " + items.length;
            gallery.classList.toggle("is-single", track.scrollWidth <= track.clientWidth + 2);
        };
        const move = function (direction) {
            const index = Math.max(0, Math.min(items.length - 1, currentIndex() + direction));
            track.scrollTo({ left: items[index].offsetLeft - items[0].offsetLeft });
        };

        prev.addEventListener("click", function () { move(-1); });
        next.addEventListener("click", function () { move(1); });
        track.addEventListener("scroll", update, { passive: true });
        window.addEventListener("resize", update);
        track.querySelectorAll("img").forEach(function (img) {
            img.addEventListener("load", update);
        });
        update();
    });
})();
