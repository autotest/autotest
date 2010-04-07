package autotest.planner;

import autotest.common.Utils;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.dom.client.HasKeyPressHandlers;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.TextBox;

public class TestPlanSelectorDisplay extends Composite implements TestPlanSelector.Display {
    
    private TextBox inputField;
    private Button show;
        
    public void initialize() {
        HTMLPanel panel = Utils.divToPanel("test_plan_selector");
        
        inputField = new TextBox();
        panel.add(inputField, "test_plan_selector_input");
        
        show = new Button("show");
        panel.add(show, "test_plan_selector_button");
        
        initWidget(panel);
    }
    
    public HasText getInputText() {
        return inputField;
    }
    
    public HasKeyPressHandlers getInputField() {
        return inputField;
    }
    
    public HasClickHandlers getShowButton() {
        return show;
    }
}
