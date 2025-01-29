<script>
  import { onMount } from "svelte";
  import { writable } from "svelte/store";
  import { isLoading } from "../../stores/loading";
  import { apiRequest } from "$lib/api";

  let restaurantView = writable({
    in_progress_orders: [],
    products: [],
    customers: [],
  });

  let productName = "";
  let productDisplay = "";
  let productPrice = "";
  let productImage = "";

  // Clear form inputs
  function clearForm() {
    productName = "";
    productDisplay = "";
    productPrice = "";
    productImage = "";
  }

  onMount(() => {
    (async () => {
      isLoading.set(true);
      const storedRestaurantView = localStorage.getItem("restaurantView");
      if (storedRestaurantView) {
        console.log("Restaurant view found in localStorage");
        const parsedRestaurantView = JSON.parse(storedRestaurantView);
        restaurantView.set(parsedRestaurantView);
      } else {
        console.log("no restaurant view found in localStorage, fetching");
        await getRestaurantView();
      }
      isLoading.set(false);
      startPolling();
    })();
  });

  let pollingInterval = null;

  function startPolling() {
    // Avoid starting multiple intervals
    if (pollingInterval) return;

    pollingInterval = setInterval(async () => {
      const data = await getRestaurantView();
      if (data.success) {
        restaurantView.set(data.restaurant_view);
        localStorage.setItem(
          "restaurantView",
          JSON.stringify(data.restaurant_view)
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

  async function handleGetRestaurantView() {
    isLoading.set(true);
    const data = await getRestaurantView();
    if (data.success) {
      restaurantView.set(data.restaurant_view);
      localStorage.setItem(
        "restaurantView",
        JSON.stringify(data.restaurant_view)
      );
    } else {
      alert(data.message);
    }
    isLoading.set(false);
  }

  async function getRestaurantView() {
    return await apiRequest("/views/restaurant", "GET");
  }

  async function handleConfirmOrder(promiseID) {
    isLoading.set(true);
    await confirmOrder(promiseID);
    isLoading.set(false);
    handleGetRestaurantView();
  }

  async function confirmOrder(promiseID) {
    return await apiRequest("/order/resolve-promise", "POST", {
      promise_id: promiseID,
    });
  }

  async function handleMarkOrderReadyForPickup(promiseID) {
    console.log(promiseID);
    isLoading.set(true);
    await markOrderReadyForPickup(promiseID);
    isLoading.set(false);
    handleGetRestaurantView();
  }

  async function markOrderReadyForPickup(promiseID) {
    return await apiRequest("/order/resolve-promise", "POST", {
      promise_id: promiseID,
    });
  }

  async function handleMarkOrderOutForDelivery(promiseID) {
    isLoading.set(true);
    await markOrderOutForDelivery(promiseID);
    isLoading.set(false);
    handleGetRestaurantView();
  }

  async function markOrderOutForDelivery(promiseID) {
    return await apiRequest("/order/resolve-promise", "POST", {
      promise_id: promiseID,
    });
  }

  async function handleAddProduct() {
    isLoading.set(true);
    const data = await addProduct();
    if (data.success) {
      await handleGetRestaurantView();
      clearForm();
    } else {
      alert(data.message);
    }
    isLoading.set(false);
  }

  async function addProduct() {
    return await apiRequest("/products/add", "POST", {
      product_name: productName,
      product_display: productDisplay,
      product_price: productPrice,
      product_image: productImage,
    });
  }

  async function handleRemoveProduct(productName) {
    isLoading.set(true);
    await removeProduct(productName);
    isLoading.set(false);
  }

  async function removeProduct(productName) {
    return await apiRequest("/products/remove", "POST", {
      product_name: productName,
    });
  }
</script>

<div class="max-w-[800px] mx-auto p-4">
  <h1 class="text-2xl text-slate-700">Restaurant app</h1>
  <div class="flex justify-between items-center mb-4">
    <h1 class="text-4xl text-slate-700 font-bold mt-8 mb-4">
      Orders in progress
    </h1>
    <button
      on:click={handleGetRestaurantView}
      class="bg-slate-700 text-white px-4 py-2 rounded hover:bg-slate-800"
    >
      Refresh
    </button>
  </div>
  <div class="border p-4 mb-8 rounded-lg shadow">
    {#if $restaurantView.in_progress_orders.length > 0}
      <div class="space-y-4">
        {#each $restaurantView.in_progress_orders as order}
          <div
            class="border rounded-lg shadow p-4 flex justify-between items-center"
          >
            <!-- Order Details -->
            <div>
              <p class="text-lg font-bold text-slate-800">
                Order ID: {order.order_id}
              </p>
              <p class="text-sm text-slate-600">
                Order date: {order.order_date}
              </p>
              <p class="text-sm text-slate-600">
                Customer name: {order.customer_name}
              </p>
              <p class="text-sm text-slate-600">
                Customer email: {order.customer_email}
              </p>
              <p class="text-sm text-slate-600">
                Delivery address: {order.customer_delivery_address}
              </p>
              <p class="mt-2 text-slate-700 font-semibold">Items:</p>
              <div class="mt-2 space-y-2">
                {#each order.order_items as item}
                  <div class="border rounded shadow-sm p-2 bg-slate-50">
                    <p class="font-medium text-slate-800">
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

            <!-- Conditional Buttons -->

            <div>
              {#if order.order_status == "driver_confirmed"}
                <div class="bg-slate-700 text-white px-4 py-2 rounded mb-4">
                  <p>Driver Accepted</p>
                </div>
              {/if}

              {#if order.order_status === "payment_complete"}
                <button
                  class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
                  on:click={() =>
                    handleConfirmOrder(
                      order.restaurant_confirmation_promise_id
                    )}
                >
                  Confirm Order
                </button>
              {:else if order.order_status === "restaurant_confirmed" || order.order_status == "driver_confirmed"}
                <button
                  class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                  on:click={() =>
                    handleMarkOrderReadyForPickup(
                      order.ready_for_pickup_promise_id
                    )}
                >
                  Ready for Pickup
                </button>
              {:else if order.order_status === "ready_for_pickup"}
                <button
                  class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                  on:click={() =>
                    handleMarkOrderOutForDelivery(
                      order.out_for_delivery_promise_id
                    )}
                >
                  Driver Picked Up
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <p class="text-slate-700">No orders in progress.</p>
    {/if}
  </div>
  <h1 class="text-4xl text-slate-700 font-bold mt-8 mb-4">Manage Products</h1>

  <!-- Add Product Section -->
  <div class="border p-4 mb-8 rounded-lg shadow">
    <h2 class="text-2xl text-slate-700 font-bold mb-4">Add New Product</h2>
    <form
      on:submit|preventDefault={handleAddProduct}
      class="flex flex-col gap-4"
    >
      <input
        type="text"
        bind:value={productName}
        placeholder="Product Name"
        class="border p-2 rounded"
        required
      />
      <input
        type="text"
        bind:value={productDisplay}
        placeholder="Product Display Name"
        class="border p-2 rounded"
        required
      />
      <input
        type="number"
        bind:value={productPrice}
        placeholder="Product Price"
        class="border p-2 rounded"
        required
      />
      <input
        type="text"
        bind:value={productImage}
        placeholder="Product Image URL"
        class="border p-2 rounded"
        required
      />
      <button
        type="submit"
        class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
      >
        Add Product
      </button>
    </form>
  </div>

  <!-- Existing Products Section -->
  <div class="border p-4 rounded-lg shadow mb-8">
    <h2 class="text-2xl text-slate-700 font-bold mb-4">Existing Products</h2>
    {#if $restaurantView.products.length > 0}
      <ul class="divide-y divide-slate-200">
        {#each $restaurantView.products as product}
          <li class="py-4 flex text-slate-700 justify-between items-center">
            <div>
              <p class="font-bold">{product.product_display}</p>
              <p>Price: ${product.product_price}</p>
              <img
                src={product.product_image}
                alt={product.product_display}
                class="w-20 h-20 object-cover mt-2"
              />
            </div>
            <button
              on:click={() => handleRemoveProduct(product.product_name)}
              class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              Remove
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p>No products found.</p>
    {/if}
  </div>
  <div class="border p-4 mb-8 rounded-lg shadow text-slate-700">
    <h2 class="text-2xl font-bold mb-4">Customers</h2>
    {#if $restaurantView.customers.length > 0}
      <ul class="divide-y divide-slate-200">
        {#each $restaurantView.customers as customer}
          <div
            class="border rounded-lg shadow p-4 flex justify-between items-center"
          >
            <p class="font-bold">{customer.customer_email}</p>
          </div>
        {/each}
      </ul>
    {:else}
      <p>No customers found.</p>
    {/if}
  </div>
</div>
