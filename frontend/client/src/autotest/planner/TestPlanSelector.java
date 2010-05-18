package autotest.planner;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.dom.client.HasKeyPressHandlers;
import com.google.gwt.event.dom.client.KeyCodes;
import com.google.gwt.event.dom.client.KeyPressEvent;
import com.google.gwt.event.dom.client.KeyPressHandler;
import com.google.gwt.user.client.ui.HasText;

import java.util.ArrayList;
import java.util.List;

public class TestPlanSelector implements ClickHandler, KeyPressHandler {

    public static interface Display {
        public HasText getInputText();
        public HasClickHandlers getShowButton();
        public HasKeyPressHandlers getInputField();
        public void setVisible(boolean visible);
    }

    public static interface Listener {
        public void onPlanSelected();
    }


    private Display display;
    private String selectedPlan;
    private List<Listener> listeners = new ArrayList<Listener>();

    public void bindDisplay(Display display) {
        this.display = display;
        display.getShowButton().addClickHandler(this);
        display.getInputField().addKeyPressHandler(this);
    }

    public void addListener(Listener listener) {
        listeners.add(listener);
    }

    @Override
    public void onClick(ClickEvent event) {
        selectPlan();
    }

    @Override
    public void onKeyPress(KeyPressEvent event) {
        if (event.getCharCode() == KeyCodes.KEY_ENTER) {
            selectPlan();
        }
    }

    private void selectPlan() {
        selectedPlan = display.getInputText().getText();
        for (Listener listener : listeners) {
            listener.onPlanSelected();
        }
    }

    public String getSelectedPlan() {
        return selectedPlan;
    }

    public void setVisible(boolean visible) {
        display.setVisible(visible);
    }
}
