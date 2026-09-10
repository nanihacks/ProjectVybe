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
                setStatus("Project search is temporarily unavailable.");
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
            modalTitle.textContent = stepNumber === 2 ? "Step 2: Project Add-ons" : "Step 1: Your Information";
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

        const getScrollStep = function () {
            const card = track.querySelector(cardSelector);
            if (!card) return scroller.clientWidth;

            const trackStyles = window.getComputedStyle(track);
            const gap = parseFloat(trackStyles.columnGap || trackStyles.gap) || 0;
            return card.getBoundingClientRect().width + gap;
        };

        const getSlideCount = function () {
            const maximumScroll = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
            const step = getScrollStep();
            return step ? Math.max(1, Math.ceil(maximumScroll / step) + 1) : 1;
        };

        const getCurrentSlide = function () {
            const step = getScrollStep();
            const slideCount = getSlideCount();
            if (!step) return 0;
            return Math.min(slideCount - 1, Math.max(0, Math.round(scroller.scrollLeft / step)));
        };

        const renderDots = function (slideCount) {
            if (!dotsContainer) return;

            dotsContainer.replaceChildren();
            for (let index = 0; index < slideCount; index += 1) {
                const dot = document.createElement("button");
                dot.type = "button";
                dot.className = "category-carousel__dot";
                dot.setAttribute("role", "tab");
                dot.setAttribute("aria-label", `Go to ${prefix} slide ${index + 1}`);
                dot.addEventListener("click", function () {
                    const maximumScroll = scroller.scrollWidth - scroller.clientWidth;
                    const target = Math.min(maximumScroll, index * getScrollStep());
                    scroller.scrollTo({ left: target, behavior: "smooth" });
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
            if (currentIndicator) currentIndicator.textContent = String(currentSlide + 1).padStart(2, "0");
            if (totalIndicator) totalIndicator.textContent = String(slideCount).padStart(2, "0");
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

            scroller.scrollTo({ left: nextPosition, behavior: "smooth" });
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
