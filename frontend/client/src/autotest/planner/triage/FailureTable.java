package autotest.planner.triage;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.HasValue;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

class FailureTable implements ClickHandler {

    public static final String[] COLUMN_NAMES = {"Machine", "Test", "Reason"};

    public static interface Display {
        public void addRow(String[] cells, boolean isNew);
        public void finalRender();
        public void setAllRowsSelected(boolean selected);
        public HasClickHandlers getSelectAllControl();
        public HasValue<Boolean> getSelectAllValue();
        public Set<Integer> getSelectedFailures();
    }

    private static class Failure {
        int id;
        String machine;
        boolean blocked;
        String testName;
        String reason;
        boolean seen;

        private Failure(int id, String machine, boolean blocked,
                String testName, String reason, boolean seen) {
            this.id = id;
            this.machine = machine;
            this.blocked = blocked;
            this.testName = testName;
            this.reason = reason;
            this.seen = seen;
        }

        public static Failure fromJsonObject(JSONObject failureObj) {
            return new Failure(
                (int) failureObj.get("id").isNumber().doubleValue(),
                failureObj.get("machine").isString().stringValue(),
                failureObj.get("blocked").isBoolean().booleanValue(),
                failureObj.get("test_name").isString().stringValue(),
                failureObj.get("reason").isString().stringValue(),
                failureObj.get("seen").isBoolean().booleanValue());
        }
    }

    private Display display;
    private List<Integer> failureIds = new ArrayList<Integer>();

    public void bindDisplay(Display display) {
        this.display = display;
        display.getSelectAllControl().addClickHandler(this);
    }

    public void addFailure(JSONObject failureObj) {
        Failure failure = Failure.fromJsonObject(failureObj);

        String machineDisplay = failure.machine;
        if (failure.blocked) {
            machineDisplay += " (blocked)";
        }

        display.addRow(
                new String[] {machineDisplay, failure.testName, failure.reason}, !failure.seen);
        failureIds.add(failure.id);
    }

    public void finishedAdding() {
        display.finalRender();
    }

    @Override
    public void onClick(ClickEvent event) {
        assert event.getSource() == display.getSelectAllControl();
        display.setAllRowsSelected(display.getSelectAllValue().getValue());
    }

    public List<Integer> getSelectedFailureIds() {
        List<Integer> selected = new ArrayList<Integer>();
        for (int i : display.getSelectedFailures()) {
            selected.add(failureIds.get(i));
        }
        return selected;
    }
}
