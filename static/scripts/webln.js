// Minimal WebLN helper for Alby (or any WebLN-capable wallet).
// This keeps all WebLN calls in one small, easy-to-test module.
window.WebLNHelper = {
  isAvailable() {
    return typeof window !== "undefined" && !!window.webln;
  },

  async enable() {
    if (!window.webln) throw new Error("WebLN not available");
    await window.webln.enable();
    return true;
  },

  async makeInvoice(amountSats, memo = "") {
    if (!window.webln) throw new Error("WebLN not available");
    // WebLN uses sats for `amount`
    return await window.webln.makeInvoice({ amount: amountSats, defaultMemo: memo });
  },

  async sendPayment(bolt11) {
    if (!window.webln) throw new Error("WebLN not available");
    return await window.webln.sendPayment(bolt11);
  },
};
