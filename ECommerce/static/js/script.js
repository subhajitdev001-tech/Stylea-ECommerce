
// ---------------------------------------------------------------------------------------------------------------------
class FlipkartBannerCarousel {
  constructor(wrapperSelector, options = {}) {
    this.wrapper =
      typeof wrapperSelector === "string"
        ? document.querySelector(wrapperSelector)
        : wrapperSelector;

    if (!this.wrapper) return;

    this.track = this.wrapper.querySelector(".hero-slider-track");
    this.prevBtn = this.wrapper.querySelector(".banner-arrow-btn-prev");
    this.nextBtn = this.wrapper.querySelector(".banner-arrow-btn-next");
    this.dotsContainer = this.wrapper.querySelector(".hero-banner-dots");

    this.originalSlides = this.track ? Array.from(this.track.children) : [];
    this.slideCount = this.originalSlides.length;
    if (this.slideCount === 0) return;

    if (this.dotsContainer) {
      this.dotsContainer.innerHTML = Array.from(
        { length: this.slideCount },
        (_, i) =>
          `<button class="hero-dot-indicator w-2 h-2 rounded-full ${i === 0 ? "active w-2.5 bg-brand-600" : "bg-slate-300"}" aria-label="Slide ${i + 1}"></button>`,
      ).join("");

      this.dots = Array.from(
        this.dotsContainer.querySelectorAll(".hero-dot-indicator"),
      );
    } else {
      this.dots = [];
    }

    this.firstClone = this.originalSlides[0].cloneNode(true);
    this.lastClone = this.originalSlides[this.slideCount - 1].cloneNode(true);

    this.track.appendChild(this.firstClone);
    this.track.insertBefore(this.lastClone, this.originalSlides[0]);

    this.currentIndex = 1;
    this.isTransitioning = false;
    this.autoplayInterval = options.interval || 6000;
    this.timer = null;

    this.track.style.transition = "none";
    this.track.style.transform = `translateX(-${this.currentIndex * 100}%)`;

    this.init();
  }

  updateDots(activeRealIndex) {
    if (!this.dots || this.dots.length === 0) return;
    this.dots.forEach((dot, idx) => {
      if (idx === activeRealIndex) {
        dot.classList.add("active", "bg-brand-600");
        dot.classList.remove("bg-slate-300");
      } else {
        dot.classList.remove("active", "bg-brand-600");
        dot.classList.add("bg-slate-300");
      }
    });
  }

  getRealIndex() {
    if (this.currentIndex === 0) return this.slideCount - 1;
    if (this.currentIndex === this.slideCount + 1) return 0;
    return this.currentIndex - 1;
  }

  goToSlide(index, animated = true) {
    if (!this.track) return;
    this.isTransitioning = true;
    this.currentIndex = index;

    if (animated) {
      this.track.style.transition =
        "transform 850ms cubic-bezier(0.25, 1, 0.5, 1)";
    } else {
      this.track.style.transition = "none";
    }

    this.track.style.transform = `translateX(-${this.currentIndex * 100}%)`;
    this.updateDots(this.getRealIndex());
  }

  next() {
    if (this.isTransitioning) return;
    this.goToSlide(this.currentIndex + 1);
  }

  prev() {
    if (this.isTransitioning) return;
    this.goToSlide(this.currentIndex - 1);
  }

  startAutoplay() {
    this.stopAutoplay();
    this.timer = setInterval(() => this.next(), this.autoplayInterval);
  }

  stopAutoplay() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  handleTransitionEnd() {
    this.isTransitioning = false;
    if (this.currentIndex === this.slideCount + 1) {
      this.currentIndex = 1;
      this.track.style.transition = "none";
      this.track.style.transform = `translateX(-${this.currentIndex * 100}%)`;
    } else if (this.currentIndex === 0) {
      this.currentIndex = this.slideCount;
      this.track.style.transition = "none";
      this.track.style.transform = `translateX(-${this.currentIndex * 100}%)`;
    }
    this.updateDots(this.getRealIndex());
  }

  init() {
    if (this.prevBtn) {
      this.prevBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.prev();
        this.startAutoplay();
      });
    }
    if (this.nextBtn) {
      this.nextBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.next();
        this.startAutoplay();
      });
    }

    this.dots.forEach((dot, realIdx) => {
      dot.addEventListener("click", () => {
        if (this.isTransitioning) return;
        this.goToSlide(realIdx + 1);
        this.startAutoplay();
      });
    });

    this.track.addEventListener("transitionend", () =>
      this.handleTransitionEnd(),
    );
    this.wrapper.addEventListener("mouseenter", () => this.stopAutoplay());
    this.wrapper.addEventListener("mouseleave", () => this.startAutoplay());

    let touchStartX = 0;
    let touchStartY = 0;

    this.wrapper.addEventListener(
      "touchstart",
      (e) => {
        this.stopAutoplay();
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
      },
      { passive: true },
    );

    this.wrapper.addEventListener(
      "touchend",
      (e) => {
        this.startAutoplay();
        const diffX = touchStartX - e.changedTouches[0].screenX;
        const diffY = touchStartY - e.changedTouches[0].screenY;
        if (Math.abs(diffX) > 45 && Math.abs(diffX) > Math.abs(diffY)) {
          if (diffX > 0) this.next();
          else this.prev();
        }
      },
      { passive: true },
    );

    this.startAutoplay();
  }
}

// Automatically initialize all sliders when the page loads
document.addEventListener("DOMContentLoaded", () => {
  // 1. Initialize Main Hero Banner
  const mainBanner = document.getElementById("mainHeroBannerWrapper");
  if (mainBanner) {
    new FlipkartBannerCarousel(mainBanner, {
      interval: 4000, // Slides change every 4 seconds
    });
  }

  // 2. Initialize Secondary Mid-Page Banner
  const secondaryBanner = document.getElementById(
    "secondaryPromoBannerWrapper",
  );
  if (secondaryBanner) {
    new FlipkartBannerCarousel(secondaryBanner, {
      interval: 5000, // Slides change every 5 seconds (slightly offset from the main banner)
    });
  }
});

function updateCategoryScrollButtons() {
  const container = document.getElementById("categoryButtonsContainer");
  const leftBtn = document.getElementById("catScrollLeftBtn");
  const rightBtn = document.getElementById("catScrollRightBtn");
  if (!container || !leftBtn || !rightBtn) return;

  const isScrollable = container.scrollWidth > container.clientWidth;
  if (!isScrollable) {
    leftBtn.classList.add("opacity-30", "pointer-events-none");
    rightBtn.classList.add("opacity-30", "pointer-events-none");
    return;
  }

  const atStart = container.scrollLeft <= 5;
  const atEnd =
    container.scrollLeft + container.clientWidth >= container.scrollWidth - 5;

  leftBtn.classList.toggle("opacity-30", atStart);
  leftBtn.classList.toggle("pointer-events-none", atStart);

  rightBtn.classList.toggle("opacity-30", atEnd);
  rightBtn.classList.toggle("pointer-events-none", atEnd);
}


// 2. Automatically apply UI styles and filter chips when the page loads
document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Check the URL for the 'gender' parameter. Default to 'all' if none exists.
    const activeDept = urlParams.get('gender') || 'all'; 

    // Reset all toggle buttons to the default white style
    const allBtns = document.querySelectorAll('.dept-btn');
    allBtns.forEach(btn => {
        btn.className = "dept-btn shrink-0 rounded-full px-5 py-2 text-xs font-bold bg-white text-slate-600 ring-1 ring-slate-200 transition hover:ring-slate-400";
    });

    // Highlight the active button based on the URL
    const activeBtn = document.getElementById(`btn-dept-${activeDept}`);
    if (activeBtn) {
        activeBtn.className = "dept-btn shrink-0 rounded-full px-5 py-2 text-xs font-bold bg-[#0f172a] text-white shadow-md transition";
    }

    // Define category mappings
    const womenCategories = [
        'sarees', 'dresses', 'one piece', 
        'jewellery', 'shoes & heels', 't-shirt & tops', 'shirt', 'jeans'
    ];
    
    const menCategories = [
        'shirts', 'suits', 'jeans & denim', 'watches', 
        'shoes', 't-shirt'
    ];

    // Filter the category chips based on the active department
    const chips = document.querySelectorAll('.subcat-chip');
    chips.forEach(chip => {
        const catName = chip.getAttribute('data-catname').toLowerCase().trim(); 
        
        // Hide redundant 'men' and 'women' chips entirely
        if (catName === 'men' || catName === 'women') {
            chip.style.display = 'none';
            return; 
        }

        if (activeDept === 'all') {
            chip.style.display = 'flex'; 
        } 
        else if (activeDept === 'women' && womenCategories.includes(catName)) {
            chip.style.display = 'flex'; 
        } 
        else if (activeDept === 'men' && menCategories.includes(catName)) {
            chip.style.display = 'flex'; 
        } 
        else {
            chip.style.display = 'none'; 
        }
    });
});

function handleSortChange(sortOption) {
  const url = new URL(window.location.href);

  if (sortOption && sortOption !== 'featured') {
      url.searchParams.set('sort', sortOption);
  } else {
      url.searchParams.delete('sort');
  }
  window.location.href = url.toString();
}

// ==========================================
// 1. DEPARTMENT & SORTING FUNCTIONS
// ==========================================

function filterDepartment(dept) {
  const url = new URL(window.location.href);
  
  // Clear both category and wishlist filters when clicking All, Women, or Men
  url.searchParams.delete('category'); 
  url.searchParams.delete('wishlist'); 

  if (dept === 'all') {
      url.searchParams.delete('gender');
      url.searchParams.delete('q'); // Also clears any active search query
  } else {
      url.searchParams.set('gender', dept);
  }

  window.location.href = url.toString();
}

function handleSortChange(sortOption) {
    const url = new URL(window.location.href);

    if (sortOption && sortOption !== 'featured') {
        url.searchParams.set('sort', sortOption);
    } else {
        url.searchParams.delete('sort');
    }

    window.location.href = url.toString();
}

// ==========================================
// 2. FLIPKART-STYLE SMART SEARCH FUNCTIONS
// ==========================================

const smartCatalogKeywords = [
    { base: 'shirt', suggestions: ['shirt for men', 'shirt under 2000', 'shirt under 1000', 'shirt for women'] },
    { base: 't-shirt', suggestions: ['t-shirt for men', 't-shirt for women', 't-shirt under 1000'] },
    { base: 'watch', suggestions: ['watch for man', 'watch under 2000', 'watches for men'] },
    { base: 'jeans', suggestions: ['jeans for men', 'jeans for women', 'jeans under 1500'] },
    { base: 'saree', suggestions: ['sarees', 'sarees under 2000', 'silk sarees'] },
    { base: 'dress', suggestions: ['dresses for women', 'one piece dress', 'dresses under 2000'] },
    { base: 'shoe', suggestions: ['shoes for men', 'shoes & heels for women', 'shoes under 2000'] },
    { base: 'suit', suggestions: ['suits for men', 'suits under 5000'] }
];

function showSearchSuggestions(query) {
    const clearBtn = document.getElementById("clearSearchBtn");
    const suggestionBox = document.getElementById("searchSuggestions");
    const suggestionList = document.getElementById("suggestionList");
    const cleanQuery = query.trim().toLowerCase();

    // If search bar is cleared, immediately reload all products if a search was active
    if (cleanQuery.length === 0) {
        if (clearBtn) clearBtn.classList.add("hidden");
        if (suggestionBox) suggestionBox.classList.add("hidden");

        const url = new URL(window.location.href);
        if (url.searchParams.has('q')) {
            url.searchParams.delete('q');
            url.searchParams.delete('category');
            url.searchParams.delete('gender');
            
            sessionStorage.setItem("focusSearch", "true");
            window.location.href = url.toString();
        }
        return;
    }

    if (clearBtn) clearBtn.classList.remove("hidden");

    let matchedSuggestions = [];

    smartCatalogKeywords.forEach(item => {
        if (item.base.startsWith(cleanQuery) || cleanQuery.startsWith(item.base)) {
            matchedSuggestions.push(...item.suggestions);
        }
    });

    if (matchedSuggestions.length === 0 && cleanQuery.split(' ').length === 1) {
        matchedSuggestions = [
            `${cleanQuery} for men`,
            `${cleanQuery} for women`,
            `${cleanQuery} under 2000`
        ];
    }

    matchedSuggestions = [...new Set([cleanQuery, ...matchedSuggestions])].slice(0, 5);

    if (suggestionList && suggestionBox) {
        suggestionList.innerHTML = matchedSuggestions.map(text => `
            <li>
                <button type="button" onclick="executeSearch('${text.replace(/'/g, "\\'")}')" class="w-full text-left px-4 py-2.5 hover:bg-slate-50 flex items-center gap-2.5 transition">
                    <i class="ph ph-magnifying-glass text-slate-400 text-sm"></i>
                    <span class="font-medium text-slate-800">${text}</span>
                </button>
            </li>
        `).join('');

        suggestionBox.classList.remove("hidden");
    }
}

function handleSearchKey(event, query) {
    if (event.key === 'Enter') {
        event.preventDefault();
        executeSearch(query);
    }
}

function executeSearch(query) {
    const url = new URL(window.location.href);
    const cleanQuery = query.trim();

    url.searchParams.delete('category');
    url.searchParams.delete('gender');

    if (cleanQuery.length > 0) {
        url.searchParams.set('q', cleanQuery);
    } else {
        url.searchParams.delete('q');
    }

    window.location.href = url.toString();
}

function clearSearch() {
    const searchInput = document.getElementById("searchInput");
    const clearBtn = document.getElementById("clearSearchBtn");
    const suggestionBox = document.getElementById("searchSuggestions");
    
    if (searchInput) searchInput.value = "";
    if (clearBtn) clearBtn.classList.add("hidden");
    if (suggestionBox) suggestionBox.classList.add("hidden");

    const url = new URL(window.location.href);
    url.searchParams.delete('q');
    url.searchParams.delete('category');
    url.searchParams.delete('gender');
    
    sessionStorage.setItem("focusSearch", "true");
    window.location.href = url.toString();
}

// ==========================================
// 3. PAGE LOAD INITIALIZATION (COMBINED)
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    
    // A. Restore Search Bar State & Focus
    const searchQuery = urlParams.get('q');
    const searchInput = document.getElementById("searchInput");
    const clearBtn = document.getElementById("clearSearchBtn");

    if (searchQuery && searchInput) {
        searchInput.value = searchQuery;
        if (clearBtn) clearBtn.classList.remove("hidden");
    }

    if (sessionStorage.getItem("focusSearch") === "true" && searchInput) {
        sessionStorage.removeItem("focusSearch");
        searchInput.focus();
    }

    // Close suggestions dropdown when clicking outside
    document.addEventListener("click", (e) => {
        const container = document.getElementById("searchContainer");
        const suggestionBox = document.getElementById("searchSuggestions");
        if (container && suggestionBox && !container.contains(e.target)) {
            suggestionBox.classList.add("hidden");
        }
    });

    // B. Highlight Active Department & Filter Category Chips
    const activeDept = urlParams.get('gender') || 'all'; 

    const allBtns = document.querySelectorAll('.dept-btn');
    allBtns.forEach(btn => {
        btn.className = "dept-btn shrink-0 rounded-full px-5 py-2 text-xs font-bold bg-white text-slate-600 ring-1 ring-slate-200 transition hover:ring-slate-400";
    });

    const activeBtn = document.getElementById(`btn-dept-${activeDept}`);
    if (activeBtn) {
        activeBtn.className = "dept-btn shrink-0 rounded-full px-5 py-2 text-xs font-bold bg-[#0f172a] text-white shadow-md transition";
    }

    const womenCategories = [
        'sarees', 'dresses', 'one piece', 
        'jewellery', 'shoes & heels', 't-shirt & tops', 'shirt', 'jeans'
    ];
    
    const menCategories = [
        'shirts', 'suits', 'jeans & denim', 'watches', 
        'shoes', 't-shirt'
    ];

    const chips = document.querySelectorAll('.subcat-chip');
    chips.forEach(chip => {
        const catName = chip.getAttribute('data-catname').toLowerCase().trim(); 
        
        if (catName === 'men' || catName === 'women') {
            chip.style.display = 'none';
            return; 
        }

        if (activeDept === 'all') {
            chip.style.display = 'flex'; 
        } else if (activeDept === 'women' && womenCategories.includes(catName)) {
            chip.style.display = 'flex'; 
        } else if (activeDept === 'men' && menCategories.includes(catName)) {
            chip.style.display = 'flex'; 
        } else {
            chip.style.display = 'none'; 
        }
    });
});

// ==========================================
// WISHLIST & CART DRAWER FUNCTIONS (NO PAGE JUMP)
// ==========================================

function toggleWishlistFilter() {
    const url = new URL(window.location.href);
    
    if (url.searchParams.get('wishlist') === 'true') {
        url.searchParams.delete('wishlist');
    } else {
        url.searchParams.set('wishlist', 'true');
        url.searchParams.delete('category');
        url.searchParams.delete('gender');
    }
    
    window.location.href = url.toString();
}

function openCart() {
    const drawer = document.getElementById("cartDrawer");
    const overlay = document.getElementById("cartOverlay");
    if (drawer && overlay) {
        overlay.classList.remove("hidden");
        drawer.classList.remove("translate-x-full");
    }
}

function closeCart() {
    const drawer = document.getElementById("cartDrawer");
    const overlay = document.getElementById("cartOverlay");
    if (drawer && overlay) {
        overlay.classList.add("hidden");
        drawer.classList.add("translate-x-full");
    }
}

// Intercept Wishlist & Cart clicks in the background so the page never reloads or scrolls to top
document.addEventListener("DOMContentLoaded", () => {
    // Restore scroll position if a fallback reload ever occurs
    const savedScrollY = sessionStorage.getItem("savedScrollY");
    if (savedScrollY !== null) {
        window.scrollTo(0, parseInt(savedScrollY, 10));
        sessionStorage.removeItem("savedScrollY");
    }

    if (sessionStorage.getItem("openCartOnLoad") === "true") {
        sessionStorage.removeItem("openCartOnLoad");
        openCart();
    }

    document.addEventListener("click", async (e) => {
        // 1. Handle Wishlist Heart Button Click Without Page Reload
        const wishlistLink = e.target.closest('a[href*="/wishlist/toggle/"]');
        if (wishlistLink) {
            e.preventDefault();
            const href = wishlistLink.getAttribute("href");

            try {
                const response = await fetch(href, { credentials: "same-origin" });
                const html = await response.text();
                const doc = new DOMParser().parseFromString(html, "text/html");

                // Update the clicked heart icon state immediately
                const updatedLink = doc.querySelector(`a[href="${href}"]`);
                if (updatedLink) {
                    wishlistLink.className = updatedLink.className;
                    wishlistLink.title = updatedLink.title;
                    wishlistLink.innerHTML = updatedLink.innerHTML;
                } else if (new URLSearchParams(window.location.search).get("wishlist") === "true") {
                    // If currently filtering by wishlist and item was removed, remove card from view
                    const card = wishlistLink.closest(".card");
                    if (card) card.remove();
                }

                // Update the header Wishlist count badge
                const currentBadge = document.getElementById("wishlistCountBadge");
                const newBadge = doc.getElementById("wishlistCountBadge");
                if (currentBadge && newBadge) {
                    currentBadge.className = newBadge.className;
                    currentBadge.textContent = newBadge.textContent.trim();
                }
            } catch (error) {
                sessionStorage.setItem("savedScrollY", window.scrollY);
                window.location.href = href;
            }
            return;
        }

        // 2. Handle Add to Cart & Cart Quantity Update Clicks Without Page Reload
        const cartLink = e.target.closest('a[href*="/cart/add/"], a[href*="/cart/update/"]');
        if (cartLink) {
            e.preventDefault();
            sessionStorage.removeItem("openCartOnLoad");
            const href = cartLink.getAttribute("href");

            try {
                const response = await fetch(href, { credentials: "same-origin" });
                const html = await response.text();
                const doc = new DOMParser().parseFromString(html, "text/html");

                // Update the header Cart count badge
                const currentCartBadge = document.getElementById("cartCountBadge");
                const newCartBadge = doc.getElementById("cartCountBadge");
                if (currentCartBadge && newCartBadge) {
                    currentCartBadge.className = newCartBadge.className;
                    currentCartBadge.textContent = newCartBadge.textContent.trim();
                }

                // Update the Slide-Out Cart Drawer contents
                const currentDrawer = document.getElementById("cartDrawer");
                const newDrawer = doc.getElementById("cartDrawer");
                if (currentDrawer && newDrawer) {
                    currentDrawer.innerHTML = newDrawer.innerHTML;
                }

                // Open the Cart Drawer smoothly at the current scroll position
                openCart();
            } catch (error) {
                sessionStorage.setItem("savedScrollY", window.scrollY);
                window.location.href = href;
            }
        }
    });
});