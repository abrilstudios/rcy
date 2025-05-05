# Prompt Engineering Guide for Issue #144

## OPTIMIZED INITIAL PROMPT

```
I'm working on Issue #144 in the RCY project to refactor the MVC architecture to implement one-way data flow patterns. Please:

1. Read these context files to understand the task:
   - /claude-guidance/144/overview.md (Start here)
   - /designs/one-way-data-flow.md
   - /designs/one-way-data-flow-diagram.md

2. Examine these implementation files to understand the current architecture:
   - /src/python/rcy_controller.py
   - /src/python/rcy_view.py 
   - /src/python/waveform_view.py

3. Continue implementing Phase [CURRENT_PHASE] of the plan, specifically [SPECIFIC_TASK].

Let me know if you need any clarification before proceeding.
```

## PROGRESS TRACKING PROMPTS

### For Getting Status Update
```
What's the current status of Issue #144 implementation? Which phases and tasks have been completed, and what are the next steps?
```

### For Task Continuation
```
Please continue implementing [SPECIFIC_COMPONENT] for the one-way data flow architecture refactoring (Issue #144). The last thing we worked on was [PREVIOUS_WORK_DESCRIPTION].
```

## TESTING PROMPTS

### For Implementation Verification
```
Please review the implementation of [COMPONENT] to verify it follows the one-way data flow pattern. Specifically, check for:

1. Proper signal blocking in view updates
2. No circular references between components
3. State changes flowing only through the dispatcher
4. Action handlers properly updating the store
```

### For Testing Specific Functionality
```
Let's test the zoom functionality in the refactored architecture. I'd like to verify:

1. Mouse wheel events are correctly captured and dispatched as zoom actions
2. The zoom center point is preserved during zoom operations
3. Zoom bounds are properly enforced
4. No recursive updates occur during zoom operations

Can you show me how this flow works in the new architecture?
```

## DEBUGGING PROMPTS

### For Circular Dependency Detection
```
I suspect there might still be a circular dependency in the [COMPONENT] implementation. Can you analyze the data flow when [ACTION] occurs and determine if there's any cyclical update pattern?
```

### For Signal Debugging
```
I'm seeing unexpected UI updates when [ACTION] occurs. Can you trace the signal-slot connections and state updates related to this action to identify what might be causing the issue?
```

## BEST PRACTICES FOR THIS PROJECT

1. **Always start with context**: Reference the claude-guidance directory and design docs before diving into implementation

2. **Maintain clear separation of concerns**: 
   - View: Only emit signals, never directly update model
   - Controller: Connect signals to actions, update view based on state
   - Store: Single source of truth for application state
   - Dispatcher: Handle actions and update store

3. **Use signal blocking consistently**: Always block signals during view updates from state changes

4. **Explain the data flow**: When implementing a feature, explain the unidirectional data flow path

5. **Focus on zoom functionality**: The primary goal is to get zoom working without circular updates

6. **Track progress systematically**: Follow the phase-by-phase implementation plan