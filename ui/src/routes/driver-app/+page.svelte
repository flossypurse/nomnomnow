<script>
  import { onMount } from "svelte";
  import { writable } from "svelte/store";
  import { isLoading } from "../../stores/loading";
  import { apiRequest } from "$lib/api";

  let driverView = writable({
    deliveries: [],
  });

  onMount(() => {
    (async () => {
      isLoading.set(true);
      //   initializeWebSocket();

      // Rename the variable to avoid overwriting the store
      const storedDriverView = localStorage.getItem("driverView");
      if (storedDriverView) {
        console.log("Driver view found in localStorage");
        const parsedDriverView = JSON.parse(storedDriverView);
        driverView.set(parsedDriverView); // Use the store's `set` method here
      } else {
        console.log("No driver view found in localStorage, fetching...");
        await getDriverView();
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
      const data = await getDriverView();
      if (data.success) {
        driverView.set(data.driver_view);
        localStorage.setItem("driverView", JSON.stringify(data.driver_view));
      }
    }, 5000);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null; // Reset interval ID
    }
  }

  async function handleGetDriverView() {
    isLoading.set(true);
    const data = await getDriverView();
    console.log(data);
    if (data.success) {
      driverView.set(data.driver_view);
      localStorage.setItem("driverView", JSON.stringify(data.driver_view));
      isLoading.set(false);
    } else {
      isLoading.set(false);
      alert(data.message);
    }
  }

  async function getDriverView() {
    // console.log(socket.id);
    return await apiRequest("/views/driver", "POST", {
      // socket_id: socket.id,
    });
  }

  async function handleConfirmOrder(promiseID) {
    isLoading.set(true);
    const data = await confirmOrder(promiseID);
    await handleGetDriverView();
    isLoading.set(false);
  }

  async function confirmOrder(promiseID) {
    return await apiRequest("/order/resolve-promise", "POST", {
      promise_id: promiseID,
    });
  }

  async function handleMarkOrderDelivered(promiseID) {
    isLoading.set(true);
    const data = await markOrderDelivered(promiseID);
    await handleGetDriverView();
    isLoading.set(false);
  }

  async function markOrderDelivered(promiseID) {
    return await apiRequest("/order/resolve-promise", "POST", {
      promise_id: promiseID,
    });
  }
</script>

<div class="max-w-[800px] mx-auto p-4">
  <h1 class="text-2xl text-slate-700">Driver app</h1>
  <div class="flex justify-between items-center mb-4">
    <h1 class="text-4xl text-slate-700 font-bold mt-8 mb-4">
      Orders to be delivered
    </h1>
    <button
      on:click={handleGetDriverView()}
      class="bg-slate-700 text-white px-4 py-2 rounded hover:bg-slate-800"
    >
      Refresh
    </button>
  </div>
  <div class="border p-4 mb-8 rounded-lg shadow">
    {#if $driverView.deliveries.length > 0}
      <div class="space-y-4">
        {#each $driverView.deliveries as order}
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
              {#if order.order_status === "restaurant_confirmed"}
                <button
                  class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
                  on:click={() =>
                    handleConfirmOrder(order.driver_confirmation_promise_id)}
                >
                  Accept Delivery
                </button>
              {:else if order.order_status === "driver_confirmed"}
                <p class="bg-slate-700 text-white px-4 py-2 rounded">
                  You have confirmed.<br />
                  Order will be ready for pickup soon.
                </p>
              {:else if order.order_status === "ready_for_pickup"}
                <p
                  class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                >
                  Ready for Pickup
                </p>
              {:else if order.order_status === "out_for_delivery"}
                <button
                  class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                  on:click={() =>
                    handleMarkOrderDelivered(
                      order.delivery_confirmation_promise_id
                    )}
                >
                  Mark as Delivered
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
</div>
