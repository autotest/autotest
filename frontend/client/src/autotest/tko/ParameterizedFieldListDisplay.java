package autotest.tko;

import autotest.tko.ParameterizedFieldListPresenter.Display;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

public class ParameterizedFieldListDisplay extends Composite implements Display {
    private static class FieldInput extends Composite implements HasText {
        private TextBox inputBox = new TextBox();

        public FieldInput(String label) {
            Panel panel = new HorizontalPanel();
            panel.add(new Label(label + ":"));
            panel.add(inputBox);
            initWidget(panel);
        }

        @Override
        public String getText() {
            return inputBox.getText();
        }

        @Override
        public void setText(String text) {
            inputBox.setText(text);
        }
    }
    
    private Panel panel = new VerticalPanel();
    
    public ParameterizedFieldListDisplay() {
        initWidget(panel);
    }

    @Override
    public HasText addFieldInput(String name) {
        FieldInput input = new FieldInput(name);
        panel.add(input);
        return input;
    }

    @Override
    public void removeFieldInput(HasText input) {
        panel.remove((Widget) input);
    }
}
