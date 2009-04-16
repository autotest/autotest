package autotest.tko;

import autotest.common.ui.ContextMenu;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;

public class TestContextMenu extends ContextMenu {
    private static TestLabelManager labelManager = TestLabelManager.getManager();
    private TestSet tests;
    private TestSelectionListener listener;
    
    public TestContextMenu(TestSet tests, TestSelectionListener listener) {
        this.tests = tests;
        this.listener = listener;
    }
    
    public boolean addViewDetailsIfSingleTest() {
        if (!tests.isSingleTest()) {
            return false;
        }
        
        addItem("View test details", new Command() {
            public void execute() {
                listener.onSelectTest(tests.getTestIndex());
            }
        });
        return true;
    }
    
    public void addLabelItems() {
        final JSONObject condition = tests.getCondition();
        addItem("Invalidate tests", new Command() {
            public void execute() {
                labelManager.handleInvalidate(condition);
            }
        });
        addItem("Revalidate tests", new Command() {
            public void execute() {
                labelManager.handleRevalidate(condition);
            }
        });
        addItem("Add label", new Command() {
            public void execute() {
                labelManager.handleAddLabels(condition);
            }
        });
        addItem("Remove label", new Command() {
            public void execute() {
                labelManager.handleRemoveLabels(condition);
            }
        });
    }
}
