# Phase 4: One-Way Data Flow & Signal Simplification
 
Goal:
Ensure a strict, unidirectional flow:
View → Controller → Model → Controller → View

Tasks:
1. Model Signals Simplification
   - Consolidate any model-level signals into a single `data_changed` event, if using PyQt signals.
   - In our code, the Controller pulls from the Model via `get_data()` rather than relying on model signals; no change required.

2. Signal Blocking in View
   - In `RcyView.update_scroll_bar()`, wrap slider updates in `blockSignals()` to prevent `valueChanged` triggering during programmatic adjustments.

3. Guard Controller Updates
   - Add an `_updating_ui` flag on `RcyController`.
   - In `update_view()`, early return if `_updating_ui` is `True`, and wrap the body in a try/finally that sets `_updating_ui`.
   - Prevents reentrant or recursive update loops.

4. Remove Deprecated Slots
   - Delete any leftover direct View→Model handlers (e.g., methods that directly call `model` from `RcyView`).

Implementation Snippets:
```python
# In RcyView.update_scroll_bar
old = self.scroll_bar.blockSignals(True)
try:
    self.scroll_bar.setPageStep(...)
finally:
    self.scroll_bar.blockSignals(old)
```

```python
# In RcyController.__init__
self._updating_ui = False

# In RcyController.update_view:
if self._updating_ui:
    return
self._updating_ui = True
try:
    # ... existing update logic
finally:
    self._updating_ui = False
```

Next Steps:
1. Apply the above guard and signal-blocking changes.
2. Write an integration test to simulate a full zoom cycle and assert no recursive calls.
3. Validate with CI and test coverage metrics.