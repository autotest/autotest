package autotest.planner.resources;

import com.google.gwt.core.client.GWT;
import com.google.gwt.resources.client.ClientBundle;
import com.google.gwt.resources.client.ImageResource;

/*
 * Based on sample code at http://code.google.com/webtoolkit/doc/latest/DevGuideClientBundle.html
 */
public interface PlannerClientBundle extends ClientBundle {
    public static final PlannerClientBundle INSTANCE = GWT.create(PlannerClientBundle.class);

    public ImageResource close();
}
