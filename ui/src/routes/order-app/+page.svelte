<script>
  import { onDestroy, onMount } from "svelte";
  import { writable, derived } from "svelte/store";
  import { isLoading } from "../../stores/loading";
  import { apiRequest } from "$lib/api";

  let customerView = writable({
    customer: {},
    orders: [],
    cart: {
      items: [],
    },
    products: [],
  });
  let isLoggedIn = writable(false);
  let autoRefresh = writable(false);
  let monitorCheckOut = writable({
    monitor: false,
    order_id: null,
  });

  let paymentModalOrder = writable(null);
  let isPaymentModalOpen = false;
  let inProgressOrderTotal = 0;
  // Variables for form inputs
  let loginEmail = ""; // Login form email input
  let createEmail = ""; // Create account form email input
  let createName = ""; // Create account form name input
  let createAddress = ""; // Create account form delivery address input

  // Status sequence for orders
  const statuses = [
    "Payment Complete",
    "Restaurant Preparing Order",
    "Driver Confirmed",
    "Order Ready for Pickup",
    "Out for Delivery",
    "Delivered",
  ];

  const statusMapping = {
    payment_complete: "Payment Complete",
    restaurant_confirmed: "Restaurant Preparing Order",
    driver_confirmed: "Driver Confirmed",
    ready_for_pickup: "Order Ready for Pickup",
    out_for_delivery: "Out for Delivery",
    delivered: "Delivered",
  };

  function getOrderStatusIndex(orderStatus) {
    return statuses.indexOf(statusMapping[orderStatus] || "Unknown Status");
  }

  onMount(async () => {
    isLoading.set(true);
    try {
      const storedCustomerView = localStorage.getItem("customerView");
      if (storedCustomerView) {
        console.log("Found customer view in localStorage");
        const parsedCustomerView = JSON.parse(storedCustomerView);
        customerView.set(parsedCustomerView);
        isLoggedIn.set(true);
      } else {
        console.log("No customer view found in localStorage");
      }
    } catch (e) {
      console.error("Error parsing localStorage data:", e);
      localStorage.removeItem("customerView"); // Clear corrupted data if necessary
    }
    isLoading.set(false);
  });

  let pollingInterval = null;

  autoRefresh.subscribe((refresh) => {
    if (refresh) {
      startPolling();
    } else {
      stopPolling();
    }
  });

  function startPolling() {
    // Avoid starting multiple intervals
    if (pollingInterval) return;

    pollingInterval = setInterval(async () => {
      const data = await getCustomerView($customerView.customer.customer_email);
      if (data.success) {
        customerView.set(data.customer_view);
        localStorage.setItem(
          "customerView",
          JSON.stringify(data.customer_view)
        );
      }
    }, 5000);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null; // Reset interval ID
    }
  }

  function handleRefreshSwitch() {
    autoRefresh.update((value) => !value);
  }

  let checkOutMonitor = null;

  monitorCheckOut.subscribe((monitor) => {
    if (monitor.monitor) {
      startCheckOutMonitor(monitor.order_id);
    } else if (checkOutMonitor) {
      clearInterval(checkOutMonitor);
      checkOutMonitor = null;
    }
  });

  function startCheckOutMonitor(order_id) {
    if (checkOutMonitor) return; // Prevent multiple intervals

    checkOutMonitor = setInterval(() => {
      const order = $customerView.orders.find((o) => o.order_id === order_id);

      if (order) {
        console.log("Checkout completed for order:", order_id);

        // Stop monitoring
        monitorCheckOut.set({ monitor: false, order_id: null });
        isLoading.set(false);

        clearInterval(checkOutMonitor);
        checkOutMonitor = null;
      }
    }, 1000);
  }

  function handleCheckOutMonitorSwitch(order) {
    monitorCheckOut.set({
      monitor: !monitorCheckOut.monitor,
      order_id: order.order_id,
    });
  }

  function togglePaymentModal() {
    isPaymentModalOpen = !isPaymentModalOpen;
  }

  async function getCustomerView(customer_email) {
    return await apiRequest("/views/customer", "POST", {
      customer_email: customer_email,
    });
  }

  async function createCustomer(
    customer_email,
    customer_name,
    customer_delivery_address
  ) {
    return await apiRequest("/customer/create", "POST", {
      customer_email: customer_email,
      customer_name: customer_name,
      customer_delivery_address: customer_delivery_address,
    });
  }

  async function getCart(customer_email) {
    console.log("Getting cart for:", customer_email);
    return await apiRequest("/cart/get", "POST", {
      customer_email: customer_email,
    });
  }

  async function addToCart(product) {
    return await apiRequest("/cart/add", "POST", {
      order_id: $customerView.cart.order_id,
      customer_email: $customerView.customer.customer_email,
      product,
    });
  }

  async function removeFromCart(item) {
    return await apiRequest("/cart/remove", "POST", {
      order_id: $customerView.cart.order_id,
      customer_email: $customerView.customer.customer_email,
      item,
    });
  }

  async function submitPayment(data) {
    return await apiRequest("/order/resolve-promise", "POST", data);
  }

  async function startCheckOut(order) {
    return await apiRequest("/order/start", "POST", {
      order_id: order.order_id,
      customer_email: $customerView.customer.customer_email,
    });
  }

  // Handle add to cart
  async function handleAddToCart(product) {
    isLoading.set(true);
    try {
      const data = await addToCart(product);
      customerView.update((current) => ({
        ...current,
        cart: data.cart,
      }));
    } catch (error) {
      console.error("Error adding product to cart:", error);
    } finally {
      isLoading.set(false);
    }
  }

  // Handle remove from cart
  async function handleRemoveFromCart(item) {
    isLoading.set(true);
    try {
      const data = await removeFromCart(item);
      console.log("Removed item from cart:", data);
      customerView.update((current) => ({
        ...current,
        cart: data.cart,
      }));
    } catch (e) {
      console.error("Error removing product from cart:", e);
    } finally {
      isLoading.set(false);
    }
  }

  async function handleStartCheckOut(order) {
    isLoading.set(true);
    const result = await startCheckOut(order);
    monitorCheckOut.set({
      monitor: true,
      order_id: order.order_id,
    });
  }

  async function handlePayForOrder(order) {
    isLoading.set(true);
    paymentModalOrder.set(order);
    togglePaymentModal();
  }

  // Handle submit payment
  async function handleSubmitPayment() {
    isLoading.set(true);
    const cardNumber = document.getElementById("cardNumber").value;
    const expiry = document.getElementById("expiry").value;
    const cvv = document.getElementById("cvv").value;
    const name = document.getElementById("name").value;
    await submitPayment({
      order_id: $customerView.cart.order_id,
      card_number: cardNumber,
      expiry: expiry,
      cvv: cvv,
      name: name,
      promise_id: $paymentModalOrder.payment_confirmation_promise_id,
    });
    togglePaymentModal();
    isLoading.set(false);
    handleGetCustomerView($customerView.customer.customer_email);
  }

  // Handle login
  async function handleGetCustomerView(customer_email) {
    isLoading.set(true);
    const data = await getCustomerView(customer_email);
    if (data.success) {
      customerView.set(data.customer_view);
      isLoggedIn.set(true);
      localStorage.setItem("customerView", JSON.stringify(data.customer_view));
      isLoading.set(false);
    } else {
      isLoading.set(false);
      alert(data.message);
    }
  }

  // Handle create account
  async function handleCreateCustomer(
    customer_email,
    customer_name,
    customer_delivery_address
  ) {
    isLoading.set(true);
    const data = await createCustomer(
      customer_email,
      customer_name,
      customer_delivery_address
    );
    isLoading.set(false);
    alert(data.message);
  }

  // Handle logout
  function handleLogout() {
    isLoading.set(true);
    customerView.set({
      orders: [],
      cart: {
        items: [],
      },
      products: [],
    });
    isLoggedIn.set(false);
    localStorage.removeItem("customerView");
    isLoading.set(false);
    console.log("Logged out successfully");
  }

  async function handleGetCart() {
    const data = await getCart($customerView.customer.customer_email);
    customerView.update((current) => ({
      ...current,
      cart: data.cart, // Set the new cart object
    }));
  }
</script>

<div class="max-w-[800px] mx-auto p-4">
  <h1 class="text-2xl text-slate-700">Order app</h1>
  {#if $isLoggedIn}
    <div class="flex justify-between items-center mt-4 mb-8">
      <!-- Left Column -->
      <div class="text-lg font-light text-slate-700">
        <p>Hi, {$customerView.customer.customer_name || "Guest"}</p>
        <p>
          Logged in as: {$customerView.customer.customer_email ||
            "Unknown Email"}
        </p>
        <p>
          Delivery address: {$customerView.customer.customer_delivery_address ||
            "Unknown Address"}
        </p>
      </div>

      <!-- Right Column: Buttons -->
      <div class="flex flex-col items-end space-y-2">
        <button
          on:click={handleLogout}
          class="bg-red-700 text-white px-4 py-2 rounded hover:bg-red-900 font-light"
        >
          Logout
        </button>
        <button
          on:click={handleRefreshSwitch}
          class="text-white px-4 py-2 rounded"
          class:bg-red-700={$autoRefresh}
          class:bg-slate-700={!$autoRefresh}
          class:hover\:bg-red-800={$autoRefresh}
          class:hover\:bg-slate-800={!$autoRefresh}
        >
          Auto Refresh
        </button>
        <button
          on:click={handleGetCustomerView(
            $customerView.customer.customer_email
          )}
          class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
        >
          Refresh Data
        </button>
      </div>
    </div>

    <h1 class="text-4xl font-bold mt-8 mb-4 text-slate-700">Select items</h1>
    <div
      class="grid grid-cols-1 md:grid-cols-2 gap-4 border p-4 mb-8 rounded-lg shadow"
    >
      {#each $customerView.products as product}
        <div
          class="border rounded-lg shadow p-4 flex flex-col items-center font-light"
        >
          <h2 class="text-lg font-semibold text-slate-700">
            {product.product_display}
          </h2>
          <img
            src={product.product_image}
            alt={product.product_display}
            class="w-32 h-32 object-cover mb-4"
          />

          <p class="text-slate-700">${product.product_price}</p>
          <button
            class="mt-4 bg-slate-700 text-white px-4 py-2 rounded hover:bg-slate-800"
            on:click={() => handleAddToCart(product)}
          >
            Add to Cart
          </button>
        </div>
      {/each}
    </div>
    <div class="flex justify-between items-center">
      <h1 class="text-4xl font-bold mt-8 mb-4 text-slate-700">Your cart</h1>
      <p class="text-lg font-light mt-8 mb-4 text-slate-700">
        {$customerView.cart.items?.length > 0
          ? $customerView.cart.cart_item_count
          : "0"}
        Items: ${$customerView.cart.items?.length > 0
          ? $customerView.cart.order_items_total
          : "0"}
      </p>
      <p class="text-lg font-light mt-8 mb-4 text-slate-700">
        Delivery Fee: ${$customerView.cart.items?.length > 0
          ? $customerView.cart.order_delivery_fee
          : "0"}
      </p>
      <p class="text-lg font-light mt-8 mb-4 text-slate-700">
        Cart Total: ${$customerView.cart.items?.length > 0
          ? $customerView.cart.order_total
          : "0"}
      </p>
    </div>
    <div class="grid grid-cols-1 gap-4 border p-4 mb-8 rounded-lg shadow">
      {#each $customerView.cart.items as item}
        <div
          class="border rounded-lg shadow p-4 flex flex-col items-center font-light"
        >
          <h2 class="text-lg font-semibold text-slate-700">
            {item.product_display}
          </h2>
          <img
            src={item.product_image}
            alt={item.product_display}
            class="w-32 h-32 object-cover mb-4"
          />

          <p class="text-slate-700">${item.product_price}</p>
          <button
            class="mt-4 bg-red-700 text-white px-4 py-2 rounded hover:bg-red-800"
            on:click={() => handleRemoveFromCart(item)}
          >
            Remove from Cart
          </button>
        </div>
      {/each}
      {#if $customerView.cart.items.length === 0}
        <p class="text-xl font-light text-slate-700">Your cart is empty.</p>
      {:else}
        <button
          class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
          on:click={() => handleStartCheckOut($customerView.cart)}
        >
          Start Checkout
        </button>
      {/if}
    </div>
    <h1 class="text-4xl font-bold mt-8 mb-4 text-slate-700">Your orders</h1>
    <div class="grid grid-cols-1 gap-4 border p-4 mb-8 rounded-lg shadow">
      {#if $customerView.orders && $customerView.orders.length > 0}
        <!-- Orders List -->
        <div class="space-y-4">
          {#each $customerView.orders as order}
            <div
              class="border rounded-lg shadow p-4 flex justify-between items-start"
            >
              <!-- Order Details -->
              <div class="mb-4">
                <h2 class="text-lg font-bold text-gray-800">
                  Order ID: {order.order_id}
                </h2>
                <p class="text-sm text-gray-600">
                  Order date: {order.order_date}
                </p>
                <p class="text-sm text-gray-600">Total: ${order.order_total}</p>

                {#if order.order_status === "payment_required"}
                  <button
                    class="mt-4 bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                    on:click={() => handlePayForOrder(order)}
                  >
                    Pay Now
                  </button>
                {/if}
                <div class="mt-2 space-y-2">
                  {#each order.order_items as item}
                    <div class="border rounded shadow-sm p-2 bg-gray-50">
                      <p class="font-medium text-gray-800">
                        {item.product_display}
                      </p>
                      <img
                        src={item.product_image}
                        alt={item.product_display}
                        class="w-16 h-16 object-cover rounded mt-2"
                      />
                    </div>
                  {/each}
                </div>
              </div>

              <!-- Status Sequence -->
              <div class="space-y-2">
                {#each statuses as status, index}
                  <div
                    class="flex items-center gap-2"
                    class:font-semibold={index <=
                      getOrderStatusIndex(order.order_status)}
                    class:text-green-500={index <=
                      getOrderStatusIndex(order.order_status)}
                    class:text-orange-500={index >
                      getOrderStatusIndex(order.order_status)}
                  >
                    <span
                      class="w-3 h-3 rounded-full"
                      class:bg-green-500={index <=
                        getOrderStatusIndex(order.order_status)}
                      class:bg-orange-500={index >
                        getOrderStatusIndex(order.order_status)}
                    ></span>
                    <p>{status}</p>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <!-- No Orders Message -->
        <p class="text-xl font-light text-slate-700">
          You have no order history.
        </p>
      {/if}
    </div>
    <!-- Backdrop -->
    <div
      id="payment-modal"
      class:hidden={!isPaymentModalOpen}
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    >
      <!-- Modal Content -->
      <div class="bg-white rounded-lg shadow-lg w-96 p-6">
        <!-- Title -->
        <h2 class="text-2xl font-semibold text-center text-gray-800 mb-4">
          Payment Details
        </h2>
        <!-- Payment Form -->
        <p>Order Total: ${$paymentModalOrder?.order_total || 0}</p>
        <form>
          <!-- Card Number -->
          <label
            for="cardNumber"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            Card Number
          </label>
          <input
            type="text"
            id="cardNumber"
            placeholder="1234 5678 9012 3456"
            class="w-full border-gray-300 rounded-lg shadow-sm p-2 mb-4"
            required
          />
          <!-- Expiry and CVV -->
          <div class="flex gap-4 mb-4">
            <div class="flex-1">
              <label
                for="expiry"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                Expiry Date
              </label>
              <input
                type="text"
                id="expiry"
                placeholder="MM/YY"
                class="w-full border-gray-300 rounded-lg shadow-sm p-2"
                required
              />
            </div>
            <div class="flex-1">
              <label
                for="cvv"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                CVV
              </label>
              <input
                type="text"
                id="cvv"
                placeholder="123"
                class="w-full border-gray-300 rounded-lg shadow-sm p-2"
                required
              />
            </div>
          </div>
          <!-- Name on Card -->
          <label
            for="name"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            Name on Card
          </label>
          <input
            type="text"
            id="name"
            placeholder="John Doe"
            class="w-full border-gray-300 rounded-lg shadow-sm p-2 mb-4"
            required
          />
          <!-- Buttons -->
          <div class="flex justify-between">
            <button
              type="button"
              class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
              on:click={togglePaymentModal}
            >
              Cancel
            </button>
            <button
              type="submit"
              class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
              on:click={() => handleSubmitPayment()}
            >
              Pay
            </button>
          </div>
        </form>
      </div>
    </div>
  {:else}
    <div>
      <h2 class="text-4xl font-bold mt-8 mb-4 text-slate-700">
        Login or Create an Account
      </h2>
      <div class="flex flex-col gap-4">
        <!-- Login Form -->
        <div>
          <h3 class="text-lg font-semibold">Login</h3>
          <form
            on:submit|preventDefault={() => handleGetCustomerView(loginEmail)}
          >
            <input
              type="email"
              bind:value={loginEmail}
              placeholder="Enter your email"
              class="border p-2 rounded w-full mb-2"
              required
            />
            <button
              type="submit"
              class="bg-blue-500 text-white px-4 py-2 rounded">Login</button
            >
          </form>
        </div>

        <!-- Create Account Form -->
        <div>
          <h3 class="text-lg font-semibold">Create an Account</h3>
          <form
            on:submit|preventDefault={() =>
              handleCreateCustomer(createEmail, createName, createAddress)}
          >
            <input
              type="email"
              bind:value={createEmail}
              placeholder="Email"
              class="border p-2 rounded w-full mb-2"
              required
            />
            <input
              type="text"
              bind:value={createName}
              placeholder="Name"
              class="border p-2 rounded w-full mb-2"
              required
            />
            <input
              type="text"
              bind:value={createAddress}
              placeholder="Delivery Address"
              class="border p-2 rounded w-full mb-2"
              required
            />
            <button
              type="submit"
              class="bg-green-500 text-white px-4 py-2 rounded"
              >Create Account</button
            >
          </form>
        </div>
      </div>
    </div>
  {/if}
</div>
